from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.observability import log_event
from app.integrations.tts.provider import TTSProviderError, get_tts_provider
from app.modules.agents.model import Agent
from app.modules.training.model import (
    RecommendationReviewStatus,
    RecommendationStrategyFeedback,
    SessionTask,
    StrategyFeedbackJudgment,
    TaskTemplate,
    TrainingPlan,
    TrainingPlanItem,
    TrainingRecommendationReview,
    TrainingSession,
    TrainingStatus,
    TrainingType,
)
from app.modules.training.recommendation_policy import (
    RECOMMENDATION_POLICY,
    analyze_trend_by_policy,
    decide_recommendation_by_policy,
    sequence_steps,
)
from app.modules.attempts.model import Attempt
from app.modules.evaluations.model import AttemptEvaluation, EvaluationMetric, EvaluationSource
from app.modules.evaluations.service import PROCESS_METRIC_NAMES
from app.modules.files.service import public_url
from app.modules.files.model import FileAsset, FileStatus, FileType
from app.modules.scoring.model import AttemptAnalysisResult
from app.modules.consent.service import require_active_consent
from app.modules.training.schema import (
    AvatarSpeechCreate,
    AvatarSpeechRead,
    FamilyObservationRead,
    Phase3DemoStatusRead,
    RecommendationEffectRead,
    RecommendationEffectSummaryRead,
    StrategyFeedbackCreate,
    StrategyFeedbackRead,
    TaskTemplateCreate,
    TaskTemplateRead,
    TaskTemplateUpdate,
    TodayTrainingRead,
    TrainingRecommendationRead,
    TrainingRecommendationReviewUpdate,
)
from app.modules.users.model import PatientProfile, User, UserRole
from app.modules.users.service import get_patient_profile


SEED_TASKS = [
    {
        "task_type": TrainingType.repeat,
        "title": "熟悉短句：天气",
        "instruction": "请跟我说这一句。",
        "target_text": "今天天气很好。",
        "content_level": "L1",
        "autonomy_level": "S1",
        "tags": ["日常", "短句", "建立信心"],
        "recommendation_weight": 95,
    },
    {
        "task_type": TrainingType.repeat,
        "title": "熟悉短句：喝水",
        "instruction": "请跟我说这一句。",
        "target_text": "我想喝一点温水。",
        "content_level": "L1",
        "autonomy_level": "S1",
        "tags": ["日常", "需求表达", "短句"],
        "recommendation_weight": 92,
    },
    {
        "task_type": TrainingType.repeat,
        "title": "连贯短句：午饭",
        "instruction": "请跟我连起来说。",
        "target_text": "我今天中午想吃米饭和青菜。",
        "content_level": "L2",
        "autonomy_level": "S1",
        "tags": ["日常", "连贯", "饮食"],
        "recommendation_weight": 88,
    },
    {
        "task_type": TrainingType.repeat,
        "title": "连贯短句：散步",
        "instruction": "请先听清楚，再完整跟读。",
        "target_text": "吃完晚饭后，我想和家人一起散步。",
        "content_level": "L3",
        "autonomy_level": "S2",
        "tags": ["家庭", "连贯", "活动"],
        "recommendation_weight": 78,
    },
    {
        "task_type": TrainingType.repeat,
        "title": "复合短句：复诊",
        "instruction": "请尽量保持声音稳定，把句子说完整。",
        "target_text": "明天上午我要去医院复诊，请帮我准备病历。",
        "content_level": "L4",
        "autonomy_level": "S2",
        "tags": ["医疗", "复合句", "计划"],
        "recommendation_weight": 70,
    },
    {
        "task_type": TrainingType.repeat,
        "title": "挑战短句：复健安排",
        "instruction": "请完整跟读这句较长的话，注意中间不要急。",
        "target_text": "这周我想每天上午练习十分钟，下午再和家人复习一遍。",
        "content_level": "L5",
        "autonomy_level": "S3",
        "tags": ["复健", "长句", "挑战"],
        "recommendation_weight": 66,
    },
    {
        "task_type": TrainingType.scenario,
        "title": "医院看病场景",
        "instruction": "你来到医院挂号处。请用自己的话说清楚你的问题和需要的帮助。",
        "target_text": "我想去医院看病，请医生帮我检查。",
        "content_level": "L3",
        "autonomy_level": "S3",
        "scene_prompt": "医院看病",
        "tags": ["医疗", "需求表达", "场景"],
        "recommendation_weight": 86,
        "scoring_config": {
            "version": "scenario-contract-v1",
            "mode": "functional_scenario",
            "agent_role": "医院挂号处工作人员",
            "opening_line": "您好，这里是挂号处。请问您今天需要办理什么？",
            "completion_response": "好的，请先到挂号窗口办理；工作人员会再告诉您对应诊室的位置。",
            "display_prompt": "你来到医院挂号处。请说清楚你的问题和需要的帮助。",
            "communication_goal": "让工作人员知道你需要就医，并能为你提供挂号、咨询或检查帮助。",
            "required_information_units": [
                {"id": "medical_intent", "label": "需要看病、挂号或咨询", "keywords": ["看病", "医院", "医生", "挂号", "检查", "就医", "门诊"]},
                {"id": "problem", "label": "哪里不舒服或遇到什么问题", "keywords": ["头疼", "头痛", "头晕", "难受", "不舒服", "疼", "发烧", "咳嗽", "不适"]},
                {"id": "request", "label": "希望对方提供什么帮助", "keywords": ["帮", "请问", "麻烦", "怎么", "哪个科", "挂", "看看", "咨询"]},
            ],
            "optional_information_units": [
                {"id": "time", "label": "症状持续多久", "keywords": ["今天", "两天", "几天", "最近", "一直", "上午", "晚上"]},
            ],
            "goal_requirements": ["medical_intent", "request"],
            "prompt_hints": ["先想一想：你想请工作人员帮什么忙？", "可以先说：我想挂号或看医生。", "再补充：你哪里不舒服，或者想问什么。"],
        },
    },
    {
        "task_type": TrainingType.scenario,
        "title": "家庭吃饭场景",
        "instruction": "家人正在准备吃饭。请用自己的话说清楚你想吃什么，或需要什么帮助。",
        "target_text": "我想少吃一点米饭，多吃一些青菜。",
        "content_level": "L2",
        "autonomy_level": "S2",
        "scene_prompt": "家庭吃饭",
        "tags": ["家庭", "饮食", "场景"],
        "recommendation_weight": 84,
        "scoring_config": {
            "version": "scenario-contract-v1", "mode": "functional_scenario",
            "agent_role": "家人",
            "opening_line": "饭快准备好了，你今天想怎么吃？",
            "completion_response": "好的，我知道你的用餐需要了，我会按你的想法准备。",
            "display_prompt": "家人正在准备吃饭。请说清楚你想吃什么，或需要什么帮助。",
            "communication_goal": "让家人理解你的饮食选择或用餐需要。",
            "required_information_units": [
                {"id": "food", "label": "想吃或不想吃什么", "keywords": ["米饭", "菜", "青菜", "面", "粥", "肉", "水果", "吃", "不要", "少", "多"]},
                {"id": "request", "label": "希望家人怎么做", "keywords": ["我想", "帮我", "给我", "少", "多", "不要", "来点"]},
            ],
            "optional_information_units": [{"id": "reason", "label": "原因或感受", "keywords": ["饿", "饱", "没胃口", "喜欢", "不想", "累"]}],
            "goal_requirements": ["food", "request"],
            "prompt_hints": ["先想一想：你想吃什么？", "可以先说：我想吃……", "再说：想要多一点、少一点，还是需要家人帮忙。"],
        },
    },
    {
        "task_type": TrainingType.scenario,
        "title": "外出购物场景",
        "instruction": "你在商店买东西。请用自己的话说清楚你想买什么，或想问什么。",
        "target_text": "请问这个多少钱？我想买两个苹果。",
        "content_level": "L3",
        "autonomy_level": "S3",
        "scene_prompt": "外出购物",
        "tags": ["生活", "购物", "场景"],
        "recommendation_weight": 76,
        "scoring_config": {
            "version": "scenario-contract-v1", "mode": "functional_scenario",
            "agent_role": "店员",
            "opening_line": "您好，需要看看什么？",
            "completion_response": "好的，我来帮你确认商品、数量和价格。",
            "display_prompt": "你在商店买东西。请说清楚你想买什么，或想问什么。",
            "communication_goal": "让店员理解你要购买的物品或需要回答的问题。",
            "required_information_units": [
                {"id": "item", "label": "想买的物品", "keywords": ["苹果", "水果", "水", "牛奶", "面包", "东西", "这个", "那个", "买"]},
                {"id": "request", "label": "购买数量、价格或需要的帮助", "keywords": ["多少", "钱", "几个", "两个", "一个", "买", "帮我", "请问"]},
            ],
            "optional_information_units": [{"id": "preference", "label": "颜色、大小或其他偏好", "keywords": ["大", "小", "红", "新鲜", "便宜", "好的"]}],
            "goal_requirements": ["item", "request"],
            "prompt_hints": ["先说：你想买什么？", "还可以问：多少钱，或想买几个。", "不用和示范句一模一样，说清楚就可以。"],
        },
    },
    {
        "task_type": TrainingType.scenario,
        "title": "家人沟通场景",
        "instruction": "请把你现在的想法或感受说给家人听，并告诉他们你希望怎么做。",
        "target_text": "我今天有点累，想先休息一会儿，晚点再训练。",
        "content_level": "L4",
        "autonomy_level": "S4",
        "scene_prompt": "家人沟通",
        "tags": ["家庭", "情绪", "自主表达"],
        "recommendation_weight": 72,
        "scoring_config": {
            "version": "scenario-contract-v1", "mode": "functional_scenario",
            "agent_role": "家人",
            "opening_line": "我在听。你现在感觉怎么样，想让我怎么帮你？",
            "completion_response": "好的，我明白你的想法了，我们按这个安排。",
            "display_prompt": "请把你现在的想法或感受说给家人听，并告诉他们你希望怎么做。",
            "communication_goal": "让家人理解你的感受、计划或需要的支持。",
            "required_information_units": [
                {"id": "state", "label": "你的感受、状态或想法", "keywords": ["累", "高兴", "难受", "想", "今天", "休息", "训练", "担心", "不舒服"]},
                {"id": "request", "label": "希望家人怎么做", "keywords": ["帮我", "让我", "先", "晚点", "一起", "不要", "需要"]},
            ],
            "optional_information_units": [{"id": "reason", "label": "原因或时间安排", "keywords": ["因为", "所以", "今天", "晚点", "一会儿", "上午", "下午"]}],
            "goal_requirements": ["state", "request"],
            "prompt_hints": ["先说一说：你现在感觉怎么样？", "再说：你希望家人怎么做。", "可以只说关键词，也可以说完整句子。"],
        },
    },
    {
        "task_type": TrainingType.scenario,
        "title": "社区问路场景",
        "instruction": "你在社区需要问路。请用自己的话说清楚你要去哪里，以及想得到什么帮助。",
        "target_text": "请问去社区卫生服务中心怎么走？我想坐电梯上去。",
        "content_level": "L5",
        "autonomy_level": "S4",
        "scene_prompt": "社区问路",
        "tags": ["社区", "问路", "自主表达"],
        "recommendation_weight": 64,
        "scoring_config": {
            "version": "scenario-contract-v1", "mode": "functional_scenario",
            "agent_role": "社区居民",
            "opening_line": "你好，需要我帮你找哪个地方吗？",
            "completion_response": "好的，我知道你要去哪里了，我来告诉你下一步该往哪边走。",
            "display_prompt": "你在社区需要问路。请说清楚你要去哪里，以及想得到什么帮助。",
            "communication_goal": "让对方理解目的地，并能够为你指路或提供通行帮助。",
            "required_information_units": [
                {"id": "destination", "label": "想去的地点", "keywords": ["社区", "医院", "卫生服务中心", "服务中心", "电梯", "楼", "那里", "地方"]},
                {"id": "request", "label": "询问路线或通行帮助", "keywords": ["怎么走", "怎么去", "请问", "帮我", "问路", "方向", "哪里", "带我"]},
            ],
            "optional_information_units": [{"id": "access", "label": "行动或通行需要", "keywords": ["电梯", "轮椅", "楼梯", "方便", "近", "远"]}],
            "goal_requirements": ["destination", "request"],
            "prompt_hints": ["先说：你要去哪里？", "再问：怎么走，或能不能帮忙。", "慢慢说清楚，不需要照着示范句说。"],
        },
    },
    {
        "task_type": TrainingType.scenario,
        "title": "药店咨询泛化探测",
        "instruction": "你来到药店。请用自己的话说明你的问题，并问清楚需要的帮助。",
        "target_text": "我最近头晕，想请药师帮我看看该怎么办。",
        "content_level": "L3",
        "autonomy_level": "S3",
        "scene_prompt": "药店咨询",
        "tags": ["医疗", "泛化探测", "非训练题"],
        "recommendation_weight": 0,
        "scoring_config": {
            "version": "scenario-contract-v1", "mode": "functional_scenario", "evaluation_role": "generalization_probe",
            "agent_role": "药师",
            "opening_line": "您好，请问您哪里不舒服，或者需要咨询什么？",
            "completion_response": "我明白你的咨询需要了，请当面向药师说明这些情况并按其指引处理。",
            "display_prompt": "你来到药店。请说清楚你的问题，并问清楚需要什么帮助。",
            "communication_goal": "让药师理解你的不适或咨询需要，并能提供下一步建议。",
            "required_information_units": [
                {"id": "problem", "label": "身体不适或咨询问题", "keywords": ["头晕", "头疼", "头痛", "难受", "不舒服", "疼", "咳嗽", "发烧", "不适"]},
                {"id": "request", "label": "希望药师提供的帮助", "keywords": ["帮", "请问", "麻烦", "什么药", "怎么办", "看看", "咨询", "建议"]},
            ],
            "optional_information_units": [{"id": "time", "label": "症状持续时间", "keywords": ["今天", "两天", "几天", "最近", "一直"]}],
            "goal_requirements": ["problem", "request"],
            "prompt_hints": ["先说：你哪里不舒服，或者想问什么。", "再说：你希望药师帮你做什么。", "这是一道新场景小测，不用说得和以前一样。"],
        },
    },
    {
        "task_type": TrainingType.scenario,
        "title": "电话预约泛化探测",
        "instruction": "你正在打电话预约服务。请用自己的话说明你要办什么，并提出请求。",
        "target_text": "你好，我想预约明天的复诊，请问还有时间吗？",
        "content_level": "L3",
        "autonomy_level": "S3",
        "scene_prompt": "电话预约",
        "tags": ["生活", "泛化探测", "非训练题"],
        "recommendation_weight": 0,
        "scoring_config": {
            "version": "scenario-contract-v1", "mode": "functional_scenario", "evaluation_role": "generalization_probe",
            "agent_role": "预约接听员",
            "opening_line": "您好，这里是预约服务，请问您想办理什么？",
            "completion_response": "好的，我知道你的预约需要了，我来继续帮你确认可安排的时间。",
            "display_prompt": "你正在打电话预约服务。请说清楚你要办什么，并提出请求。",
            "communication_goal": "让接听者理解预约或办理需求，并能安排下一步。",
            "required_information_units": [
                {"id": "purpose", "label": "预约或办理的事情", "keywords": ["预约", "复诊", "挂号", "明天", "时间", "办理", "看医生"]},
                {"id": "request", "label": "向对方提出请求或询问", "keywords": ["请问", "帮", "麻烦", "可以", "还有", "吗", "安排"]},
            ],
            "optional_information_units": [{"id": "time", "label": "希望的时间", "keywords": ["明天", "上午", "下午", "几点", "今天"]}],
            "goal_requirements": ["purpose", "request"],
            "prompt_hints": ["先说：你想预约或办理什么。", "再问：有没有时间，或能不能帮忙安排。", "这是一道新场景小测，用自己的话说清楚即可。"],
        },
    },
]


def ensure_seed_tasks(db: Session) -> None:
    existing = {item.title: item for item in db.scalars(select(TaskTemplate))}
    changed = False
    for seed in SEED_TASKS:
        item = _complete_seed_dialogue_contract(deepcopy(seed))
        template = existing.get(item["title"])
        if template:
            for field in [
                "task_type",
                "instruction",
                "target_text",
                "content_level",
                "autonomy_level",
                "scene_prompt",
                "scoring_config",
                "tags",
                "recommendation_weight",
            ]:
                if field in item and getattr(template, field) != item[field]:
                    setattr(template, field, item[field])
                    changed = True
            if not template.is_active:
                template.is_active = True
                changed = True
            continue
        # Older repeat seeds have no explicit contract; add their default before
        # construction instead of passing scoring_config twice.
        seed_data = {**item, "scoring_config": item.get("scoring_config", {"mode": "repeat"})}
        db.add(TaskTemplate(**seed_data))
        changed = True
    legacy = existing.get("短句跟读")
    if legacy and legacy.is_active:
        legacy.is_active = False
        changed = True
    if changed:
        db.commit()


def _complete_seed_dialogue_contract(item: dict) -> dict:
    """Backfill the explicit dialogue fields for maintained scenario seed tasks."""
    if item.get("task_type") != TrainingType.scenario:
        return item
    contract = item.get("scoring_config") or {}
    if contract.get("mode") != "functional_scenario":
        return item
    contract.setdefault("opening_line", "您好，请问有什么需要帮助的吗？")
    contract.setdefault("minimum_patient_turns", 2)
    contract.setdefault("maximum_patient_turns", 5)
    contract.setdefault("completion_response", "好的，我已了解你的需要。接下来请按现场工作人员的指引办理。")
    units = contract.get("required_information_units") or []
    contract.setdefault(
        "follow_up_questions",
        [
            {"target_information_unit": unit.get("id"), "question": f"为了更好地帮助你，能再说说{unit.get('label', '这方面的信息')}吗？"}
            for unit in units
            if isinstance(unit, dict) and unit.get("id")
        ],
    )
    item["scoring_config"] = contract
    return item


def get_training_types() -> list[str]:
    return [TrainingType.repeat.value, TrainingType.scenario.value]


def list_task_templates(
    db: Session,
    training_type: TrainingType | None = None,
    include_inactive: bool = False,
) -> list[TaskTemplateRead]:
    ensure_seed_tasks(db)
    stmt = select(TaskTemplate).order_by(
        TaskTemplate.task_type.asc(),
        TaskTemplate.content_level.asc(),
        TaskTemplate.autonomy_level.asc(),
        TaskTemplate.recommendation_weight.desc(),
    )
    if training_type:
        stmt = stmt.where(TaskTemplate.task_type == training_type)
    if not include_inactive:
        stmt = stmt.where(TaskTemplate.is_active.is_(True))
    return [TaskTemplateRead.model_validate(item) for item in db.scalars(stmt)]


def is_generalization_probe(template: TaskTemplate) -> bool:
    return (template.scoring_config or {}).get("evaluation_role") == "generalization_probe"


def has_functional_scenario_contract(template: TaskTemplate) -> bool:
    """Return whether a template is safe to offer as free-expression training.

    Older databases can contain scenario templates created before scoring contracts
    existed. They must remain editable by therapists, but must never be assigned to
    patients where they could fall back to reference-sentence alignment.
    """
    if template.task_type != TrainingType.scenario:
        return True
    try:
        _validate_scenario_contract(template.task_type, template.scoring_config)
    except HTTPException:
        return False
    return True


def create_task_template(db: Session, payload: TaskTemplateCreate) -> TaskTemplateRead:
    _validate_scenario_contract(payload.task_type, payload.scoring_config)
    template = TaskTemplate(
        task_type=payload.task_type,
        title=payload.title.strip(),
        instruction=payload.instruction.strip(),
        target_text=payload.target_text.strip(),
        content_level=payload.content_level.strip() or "L1",
        autonomy_level=payload.autonomy_level.strip() or "S1",
        scene_prompt=payload.scene_prompt.strip() if payload.scene_prompt else None,
        scoring_config=payload.scoring_config,
        tags=[item.strip() for item in payload.tags if item.strip()],
        recommendation_weight=max(0, min(payload.recommendation_weight, 100)),
        is_active=payload.is_active,
    )
    if not template.title or not template.instruction or not template.target_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="训练材料标题、说明和文本不能为空")
    db.add(template)
    db.commit()
    db.refresh(template)
    return TaskTemplateRead.model_validate(template)


def update_task_template(db: Session, template_id: UUID, payload: TaskTemplateUpdate) -> TaskTemplateRead:
    template = db.get(TaskTemplate, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练材料不存在")
    for field in ["title", "instruction", "target_text", "content_level", "autonomy_level", "scene_prompt", "scoring_config"]:
        value = getattr(payload, field)
        if value is not None:
            setattr(template, field, value.strip() if isinstance(value, str) else value)
    if payload.tags is not None:
        template.tags = [item.strip() for item in payload.tags if item.strip()]
    if payload.recommendation_weight is not None:
        template.recommendation_weight = max(0, min(payload.recommendation_weight, 100))
    if payload.is_active is not None:
        template.is_active = payload.is_active
    _validate_scenario_contract(template.task_type, template.scoring_config)
    if not template.title or not template.instruction or not template.target_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="训练材料标题、说明和文本不能为空")
    db.commit()
    db.refresh(template)
    return TaskTemplateRead.model_validate(template)


def _validate_scenario_contract(task_type: TrainingType, scoring_config: dict | None) -> None:
    """Keep free-expression tasks from silently falling back to sentence matching."""
    if task_type != TrainingType.scenario:
        return
    config = scoring_config or {}
    required_units = config.get("required_information_units")
    if (
        config.get("mode") != "functional_scenario"
        or not isinstance(config.get("version"), str)
        or not config["version"].strip()
        or not isinstance(config.get("display_prompt"), str)
        or not config["display_prompt"].strip()
        or not isinstance(config.get("communication_goal"), str)
        or not config["communication_goal"].strip()
        or not isinstance(required_units, list)
        or len(required_units) < 2
        or not isinstance(config.get("goal_requirements"), list)
        or not config["goal_requirements"]
        or not isinstance(config.get("prompt_hints"), list)
        or not any(isinstance(hint, str) and hint.strip() for hint in config["prompt_hints"])
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="场景表达必须配置功能性沟通评分契约：目标、至少两个关键信息单元和分级提示。",
        )
    unit_ids = set()
    for unit in required_units:
        if (
            not isinstance(unit, dict)
            or not isinstance(unit.get("id"), str)
            or not unit["id"].strip()
            or not isinstance(unit.get("label"), str)
            or not unit["label"].strip()
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="场景表达的信息单元格式不完整。")
        if (
            not isinstance(unit.get("keywords"), list)
            or not any(isinstance(keyword, str) and keyword.strip() for keyword in unit["keywords"])
            or unit["id"] in unit_ids
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="每个场景信息单元至少需要一个可接受表达。")
        unit_ids.add(unit["id"])
    if not set(config["goal_requirements"]).issubset(unit_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="场景沟通目标引用了不存在的信息单元。")


def get_training_recommendation(db: Session, user: User) -> TrainingRecommendationRead:
    ensure_seed_tasks(db)
    profile = get_patient_profile(db, user)
    return get_patient_training_recommendation(db, profile.id, include_review_override=True)


def get_patient_training_recommendation(
    db: Session,
    patient_profile_id: UUID,
    include_review_override: bool = True,
) -> TrainingRecommendationRead:
    ensure_seed_tasks(db)
    from app.modules.profiles.service import refresh_ability_profile

    ability = refresh_ability_profile(db, patient_profile_id)
    recent_effects = recent_recommendation_effects_by_profile(db, patient_profile_id)
    completed_effects = [effect for effect in reversed(recent_effects) if effect.status == TrainingStatus.completed.value and effect.metrics]
    trend = analyze_trend_by_policy(completed_effects)
    decision = decide_recommendation_by_policy(ability, trend)
    manual_note = latest_recommendation_note(db, patient_profile_id)
    system_recommendation = build_recommendation_read(
        db=db,
        recommended_type=decision.recommended_type,
        headline=decision.headline,
        reason=decision.reason,
        focus_points=decision.focus_points,
        suggested_minutes=decision.suggested_minutes,
        content_level=decision.content_level,
        autonomy_level=decision.autonomy_level,
        confidence=ability.confidence,
        profile_summary=ability.assessment_summary,
        source="system",
        review_status=RecommendationReviewStatus.pending_review.value,
        therapist_notes=manual_note.next_strategy if manual_note else None,
        updated_at=manual_note.created_at if manual_note else None,
        adaptation_note=decision.adaptation_note,
        reminder=trend.patient_reminder,
    )
    return system_recommendation


def get_patient_recommendation_for_therapist(db: Session, patient_user_id: UUID) -> TrainingRecommendationRead:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    return get_patient_training_recommendation(db, profile.id, include_review_override=False)


def save_patient_recommendation_review(
    db: Session,
    therapist: User,
    patient_user_id: UUID,
    payload: TrainingRecommendationReviewUpdate,
) -> TrainingRecommendationRead:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    system_recommendation = get_patient_training_recommendation(db, profile.id, include_review_override=False)
    status_value = (
        RecommendationReviewStatus.confirmed
        if payload.recommended_type == system_recommendation.recommended_type
        and payload.headline == system_recommendation.headline
        and payload.reason == system_recommendation.reason
        and payload.focus_points == system_recommendation.focus_points
        and payload.suggested_minutes == system_recommendation.suggested_minutes
        else RecommendationReviewStatus.adjusted
    )
    review = TrainingRecommendationReview(
        patient_profile_id=profile.id,
        recommended_type=payload.recommended_type,
        headline=payload.headline.strip() or system_recommendation.headline,
        reason=payload.reason.strip() or system_recommendation.reason,
        focus_points=[point.strip() for point in payload.focus_points if point.strip()][:5],
        suggested_minutes=max(5, min(payload.suggested_minutes, 30)),
        content_level=system_recommendation.content_level,
        autonomy_level=system_recommendation.autonomy_level,
        confidence=system_recommendation.confidence,
        profile_summary=system_recommendation.profile_summary,
        review_status=status_value,
        reviewed_by_user_id=therapist.id,
        therapist_notes=payload.therapist_notes,
    )
    if not review.focus_points:
        review.focus_points = system_recommendation.focus_points
    db.add(review)
    db.commit()
    db.refresh(review)
    return recommendation_review_to_read(db, review)


def get_patient_recommendation_effects(db: Session, patient_user_id: UUID) -> RecommendationEffectSummaryRead:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    effects = recent_recommendation_effects_by_profile(db, profile.id)
    completed_count = sum(1 for effect in effects if effect.status == TrainingStatus.completed.value)
    matched_count = sum(1 for effect in effects if effect.recommendation_matched)
    trend = analyze_recommendation_trend(effects)
    return RecommendationEffectSummaryRead(
        total_recommended_sessions=len(effects),
        completed_recommended_sessions=completed_count,
        matched_sessions=matched_count,
        trend_status=trend["status"],
        trend_summary=trend["summary"],
        strategy_hint=trend["hint"],
        evidence_points=trend["evidence"],
        attribution_points=trend["attribution_points"],
        reminder_level=trend["reminder_level"],
        patient_reminder=trend["patient_reminder"],
        family_reminder=trend["family_reminder"],
        therapist_reminder=trend["therapist_reminder"],
        latest=effects,
    )


def recent_recommendation_effects_by_profile(db: Session, patient_profile_id: UUID) -> list[RecommendationEffectRead]:
    sessions = list(
        db.scalars(
            select(TrainingSession)
            .where(
                TrainingSession.patient_profile_id == patient_profile_id,
                TrainingSession.recommendation_source.is_not(None),
            )
            .order_by(TrainingSession.created_at.desc())
            .limit(8)
        )
    )
    return [build_recommendation_effect(db, session) for session in sessions]


def create_strategy_feedback(
    db: Session,
    therapist: User,
    patient_user_id: UUID,
    payload: StrategyFeedbackCreate,
) -> StrategyFeedbackRead:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    effects = get_patient_recommendation_effects(db, patient_user_id)
    try:
        judgment = StrategyFeedbackJudgment(payload.judgment)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="策略反馈判断无效") from exc
    feedback = RecommendationStrategyFeedback(
        patient_profile_id=profile.id,
        therapist_user_id=therapist.id,
        trend_status=effects.trend_status,
        judgment=judgment,
        reason=payload.reason,
        next_strategy=payload.next_strategy,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return StrategyFeedbackRead.model_validate(feedback)


def latest_strategy_feedback(db: Session, patient_profile_id: UUID) -> RecommendationStrategyFeedback | None:
    return db.scalar(
        select(RecommendationStrategyFeedback)
        .where(RecommendationStrategyFeedback.patient_profile_id == patient_profile_id)
        .order_by(RecommendationStrategyFeedback.created_at.desc())
    )


def latest_recommendation_note(db: Session, patient_profile_id: UUID) -> RecommendationStrategyFeedback | None:
    return db.scalar(
        select(RecommendationStrategyFeedback)
        .where(
            RecommendationStrategyFeedback.patient_profile_id == patient_profile_id,
            RecommendationStrategyFeedback.trend_status == "manual_note",
        )
        .order_by(RecommendationStrategyFeedback.created_at.desc())
    )


def get_family_observation(db: Session) -> FamilyObservationRead:
    patient = first_patient(db)
    if not patient:
        return FamilyObservationRead(
            patient_username="暂无患者",
            training_count=0,
            completed_recommended_sessions=0,
            recommendation_headline="暂无训练建议",
            recommendation_source="system",
            trend_summary="还没有可观察的训练记录。",
            strategy_hint="请等待患者完成训练后再查看。",
            therapist_note=None,
            reminder_level="info",
            family_reminder="患者完成训练后，这里会显示陪伴提醒。",
            current_level_label="等待开始",
            progress_label="暂无趋势",
        progress_percent=0,
        level_items=family_empty_level_items(),
        trend_items=[],
        recent_records=[],
    )
    return build_family_observation_for_patient(db, patient.id)


def build_family_observation_for_patient(
    db: Session,
    patient_user_id: UUID,
    bound_patients: list[dict] | None = None,
) -> FamilyObservationRead:
    patient = db.get(User, patient_user_id)
    if not patient or patient.role != UserRole.patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者不存在")
    profile = get_patient_profile_by_user_id(db, patient.id)
    recommendation = get_patient_training_recommendation(db, profile.id, include_review_override=True)
    effects = get_patient_recommendation_effects(db, patient.id)
    feedback = latest_strategy_feedback(db, profile.id)
    training_count = db.scalar(select(func.count(TrainingSession.id)).where(TrainingSession.patient_profile_id == profile.id))
    last_training_at = latest_training_at(db, profile.id)
    family_visuals = build_family_visuals(effects)
    return FamilyObservationRead(
        patient_username=patient.username,
        training_count=training_count or 0,
        completed_recommended_sessions=effects.completed_recommended_sessions,
        last_training_at=last_training_at,
        adherence_summary=family_adherence_summary(training_count or 0, effects.completed_recommended_sessions, last_training_at),
        recommendation_headline=recommendation.headline,
        recommendation_source=recommendation.source,
        trend_summary=effects.trend_summary,
        strategy_hint=feedback.next_strategy if feedback and feedback.next_strategy else effects.family_reminder or effects.strategy_hint,
        therapist_note=feedback.reason if feedback and feedback.reason else recommendation.therapist_notes,
        reminder_level=effects.reminder_level,
        family_reminder=effects.family_reminder,
        current_level_label=family_visuals["current_level_label"],
        progress_label=family_visuals["progress_label"],
        progress_percent=family_visuals["progress_percent"],
        level_items=family_visuals["level_items"],
        trend_items=family_visuals["trend_items"],
        recent_records=family_recent_training_records(db, profile.id),
        bound_patients=bound_patients or [],
        selected_patient_user_id=patient.id,
    )


def latest_training_at(db: Session, patient_profile_id: UUID):
    return db.scalar(
        select(func.max(Attempt.created_at))
        .join(SessionTask, SessionTask.id == Attempt.session_task_id)
        .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
        .where(TrainingSession.patient_profile_id == patient_profile_id)
    )


def family_adherence_summary(training_count: int, completed_recommended_sessions: int, last_training_at) -> str:
    if training_count <= 0:
        return "还没有训练记录，可以先陪他完成一次短句练习。"
    if completed_recommended_sessions <= 0:
        return f"已经练了 {training_count} 次，但还没有完成建议训练，可以先陪他按今日建议完成一组。"
    if last_training_at:
        return f"已经练了 {training_count} 次，其中 {completed_recommended_sessions} 次完成建议训练，最近一次在 {last_training_at.strftime('%m月%d日')}。"
    return f"已经练了 {training_count} 次，其中 {completed_recommended_sessions} 次完成建议训练。"


def build_family_visuals(effects: RecommendationEffectSummaryRead) -> dict:
    latest = effects.latest[0] if effects.latest else None
    metrics = latest.metrics if latest else {}
    accuracy = metrics.get("script_accuracy")
    errors = metrics.get("error_count")
    speech_rate = metrics.get("speech_rate")
    loudness = metrics.get("loudness")
    progress_percent = family_progress_percent(accuracy, errors)
    return {
        "current_level_label": family_level_label(progress_percent, effects.completed_recommended_sessions),
        "progress_label": family_progress_label(effects.trend_status),
        "progress_percent": progress_percent,
        "level_items": [
            {
                "key": "expression",
                "label": "表达完整度",
                "icon": "message-circle",
                "value": family_value_label(accuracy, "%"),
                "level": progress_percent,
                "tone": family_tone_from_percent(progress_percent),
                "hint": "能不能把一句话比较完整地说出来。",
            },
            {
                "key": "stability",
                "label": "稳定度",
                "icon": "shield-check",
                "value": "较稳" if errors is not None and errors <= 1 else "需陪伴" if errors is not None else "观察中",
                "level": family_stability_percent(errors),
                "tone": family_tone_from_percent(family_stability_percent(errors)),
                "hint": "错误和停顿越少，说明练习越稳定。",
            },
            {
                "key": "rhythm",
                "label": "说话节奏",
                "icon": "audio-lines",
                "value": family_rhythm_label(speech_rate),
                "level": family_rhythm_percent(speech_rate),
                "tone": family_tone_from_percent(family_rhythm_percent(speech_rate)),
                "hint": "不是越快越好，平稳、能听清更重要。",
            },
            {
                "key": "voice",
                "label": "声音状态",
                "icon": "volume-2",
                "value": family_voice_label(loudness),
                "level": family_voice_percent(loudness),
                "tone": family_tone_from_percent(family_voice_percent(loudness)),
                "hint": "声音保持自然、清楚即可。",
            },
        ],
        "trend_items": family_trend_items(effects.latest),
    }


def family_empty_level_items() -> list[dict]:
    return [
        {"key": "expression", "label": "表达完整度", "icon": "message-circle", "value": "待训练", "level": 0, "tone": "muted", "hint": "完成训练后自动显示。"},
        {"key": "stability", "label": "稳定度", "icon": "shield-check", "value": "待训练", "level": 0, "tone": "muted", "hint": "完成训练后自动显示。"},
        {"key": "rhythm", "label": "说话节奏", "icon": "audio-lines", "value": "待训练", "level": 0, "tone": "muted", "hint": "完成训练后自动显示。"},
        {"key": "voice", "label": "声音状态", "icon": "volume-2", "value": "待训练", "level": 0, "tone": "muted", "hint": "完成训练后自动显示。"},
    ]


def family_progress_percent(accuracy: float | None, errors: float | None) -> int:
    if accuracy is None:
        return 0
    score = accuracy
    if errors is not None:
        score -= min(max(errors - 1, 0), 5) * 4
    return int(max(0, min(round(score), 100)))


def family_level_label(percent: int, completed_count: int) -> str:
    if completed_count == 0:
        return "正在建立记录"
    if percent >= 90:
        return "表现稳定"
    if percent >= 75:
        return "稳步练习中"
    if percent >= 55:
        return "需要多陪伴"
    return "先建立信心"


def family_progress_label(status: str) -> str:
    if status == "effective":
        return "正在进步"
    if status == "needs_adjustment":
        return "需要调整"
    if status == "mixed":
        return "有波动"
    return "继续观察"


def family_value_label(value: float | None, unit: str) -> str:
    if value is None:
        return "观察中"
    return f"{value:g}{unit}"


def family_tone_from_percent(percent: int) -> str:
    if percent >= 85:
        return "good"
    if percent >= 65:
        return "steady"
    if percent > 0:
        return "watch"
    return "muted"


def family_stability_percent(errors: float | None) -> int:
    if errors is None:
        return 0
    return int(max(20, min(100, 100 - errors * 18)))


def family_rhythm_percent(speech_rate: float | None) -> int:
    if speech_rate is None:
        return 0
    return int(max(25, min(100, 100 - abs(speech_rate - 210) * 0.7)))


def family_voice_percent(loudness: float | None) -> int:
    if loudness is None:
        return 0
    return int(max(25, min(100, 100 - abs(loudness - 69) * 3)))


def family_rhythm_label(speech_rate: float | None) -> str:
    if speech_rate is None:
        return "观察中"
    if speech_rate < 180:
        return "偏慢"
    if speech_rate > 240:
        return "偏快"
    return "平稳"


def family_voice_label(loudness: float | None) -> str:
    if loudness is None:
        return "观察中"
    if loudness < -35:
        return "偏轻"
    if loudness > -12:
        return "偏响"
    return "清楚"


def family_trend_items(effects: list[RecommendationEffectRead]) -> list[dict]:
    completed = [effect for effect in reversed(effects) if effect.status == TrainingStatus.completed.value and effect.metrics]
    if not completed:
        return []
    recent = completed[-4:]
    items = []
    for index, effect in enumerate(recent, start=1):
        percent = family_progress_percent(effect.metrics.get("script_accuracy"), effect.metrics.get("error_count"))
        items.append(
            {
                "label": f"第 {index} 次",
                "value": percent,
                "summary": effect.summary,
                "created_at": effect.created_at.isoformat(),
            }
        )
    return items


def family_recent_training_records(db: Session, patient_profile_id: UUID, limit: int = 5) -> list[dict]:
    rows = db.execute(
        select(Attempt, TrainingSession, SessionTask, AttemptAnalysisResult)
        .join(SessionTask, SessionTask.id == Attempt.session_task_id)
        .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
        .outerjoin(AttemptAnalysisResult, AttemptAnalysisResult.attempt_id == Attempt.id)
        .where(TrainingSession.patient_profile_id == patient_profile_id)
        .order_by(Attempt.created_at.desc())
        .limit(limit)
    ).all()
    records = []
    for attempt, session, task, analysis in rows:
        metrics = attempt_process_metrics(db, attempt.id)
        records.append(
            {
                "attempt_id": str(attempt.id),
                "created_at": attempt.created_at.isoformat(),
                "training_type": session.training_type.value,
                "task_title": task.task_template.title,
                "target_text": task.task_template.target_text,
                "audio_url": public_url(attempt.audio_file) if attempt.audio_file else None,
                "asr_text": analysis.asr_text if analysis else None,
                "summary": family_record_summary(metrics, attempt.analysis_status.value),
                "metrics": metrics,
            }
        )
    return records


def attempt_process_metrics(db: Session, attempt_id: UUID) -> dict[str, float]:
    rows = db.execute(
        select(EvaluationMetric.name, AttemptEvaluation.value)
        .join(AttemptEvaluation, AttemptEvaluation.metric_id == EvaluationMetric.id)
        .where(
            AttemptEvaluation.attempt_id == attempt_id,
            AttemptEvaluation.evaluation_source == EvaluationSource.system_rule,
            EvaluationMetric.name.in_(PROCESS_METRIC_NAMES),
        )
    ).all()
    return {name: round(float(value), 1) for name, value in rows}


def family_record_summary(metrics: dict[str, float], status: str) -> str:
    if status != TrainingStatus.completed.value:
        return "这次训练还没有完成分析。"
    accuracy = metrics.get("script_accuracy")
    errors = metrics.get("error_count")
    if accuracy is None:
        return "这次训练已保存，暂时没有完整评分。"
    if accuracy >= 90 and (errors is None or errors <= 1):
        return "这次表达比较完整，状态较稳定。"
    if accuracy >= 70:
        return "这次能完成主要内容，可以继续陪伴巩固。"
    return "这次有些地方没有说完整，陪伴时可以先练短句。"


def get_phase3_demo_status(db: Session) -> Phase3DemoStatusRead:
    patient = first_patient(db)
    if not patient:
        return Phase3DemoStatusRead(
            has_patient=False,
            has_recommendation=False,
            has_therapist_review=False,
            has_recommended_training=False,
            has_effect_trend=False,
            has_strategy_feedback=False,
            next_step="先创建或准备一个患者账号。",
        )
    profile = get_patient_profile_by_user_id(db, patient.id)
    recommendation = get_patient_training_recommendation(db, profile.id, include_review_override=True)
    review = latest_recommendation_review(db, profile.id)
    effects = get_patient_recommendation_effects(db, patient.id)
    feedback = latest_strategy_feedback(db, profile.id)
    has_effect_trend = effects.completed_recommended_sessions >= 1
    return Phase3DemoStatusRead(
        has_patient=True,
        has_recommendation=bool(recommendation.headline),
        has_therapist_review=bool(review and review.review_status in {RecommendationReviewStatus.confirmed, RecommendationReviewStatus.adjusted}),
        has_recommended_training=effects.total_recommended_sessions > 0,
        has_effect_trend=has_effect_trend,
        has_strategy_feedback=feedback is not None,
        next_step=phase3_next_step(review, effects, feedback),
    )


def first_patient(db: Session) -> User | None:
    return db.scalar(select(User).where(User.role == UserRole.patient).order_by(User.created_at.asc()))


def phase3_next_step(
    review: TrainingRecommendationReview | None,
    effects: RecommendationEffectSummaryRead,
    feedback: RecommendationStrategyFeedback | None,
) -> str:
    if not review:
        return "治疗师复核一次训练推荐。"
    if effects.total_recommended_sessions == 0:
        return "患者从推荐入口完成一次训练。"
    if effects.completed_recommended_sessions == 0:
        return "患者上传录音并生成反馈。"
    if not feedback:
        return "治疗师记录一次策略反馈。"
    return "Phase 3 演示闭环已打通。"


def build_recommendation_effect(db: Session, session: TrainingSession) -> RecommendationEffectRead:
    metrics = recommendation_session_metrics(db, session.id)
    return RecommendationEffectRead(
        session_id=session.id,
        created_at=session.created_at,
        training_type=session.training_type,
        recommendation_source=session.recommendation_source,
        recommendation_headline=(session.recommendation_snapshot or {}).get("headline"),
        recommendation_matched=session.recommendation_matched,
        status=session.status.value,
        metrics=metrics,
        summary=effect_summary(metrics, session.status == TrainingStatus.completed),
    )


def recommendation_session_metrics(db: Session, session_id: UUID) -> dict[str, float]:
    rows = db.execute(
        select(EvaluationMetric.name, AttemptEvaluation.value)
        .join(AttemptEvaluation, AttemptEvaluation.metric_id == EvaluationMetric.id)
        .join(Attempt, Attempt.id == AttemptEvaluation.attempt_id)
        .join(SessionTask, SessionTask.id == Attempt.session_task_id)
        .where(
            SessionTask.training_session_id == session_id,
            AttemptEvaluation.evaluation_source == EvaluationSource.system_rule,
            EvaluationMetric.name.in_(PROCESS_METRIC_NAMES),
        )
    ).all()
    grouped: dict[str, list[float]] = {}
    for metric_name, value in rows:
        grouped.setdefault(metric_name, []).append(float(value))
    return {name: round(sum(values) / len(values), 1) for name, values in grouped.items() if values}


def effect_summary(metrics: dict[str, float], completed: bool) -> str:
    if not completed:
        return "患者已从推荐入口开始训练，但还没有完成评分。"
    if not metrics:
        return "训练已完成，暂时没有可汇总的过程指标。"
    parts = []
    accuracy = metrics.get("script_accuracy")
    errors = metrics.get("error_count")
    speech_rate = metrics.get("speech_rate")
    loudness = metrics.get("loudness")
    if accuracy is not None:
        parts.append("表达完整度较好" if accuracy >= 90 else "表达完整度仍需关注")
    if errors is not None:
        parts.append("错误较少" if errors <= 1 else "错误仍偏多")
    if speech_rate is not None:
        parts.append("节奏稳定" if 180 <= speech_rate <= 240 else "节奏需要继续观察")
    if loudness is not None:
        parts.append("音量稳定" if -35 <= loudness <= -12 else "音量需要继续观察")
    return "；".join(parts) + "。"


def analyze_recommendation_trend(effects: list[RecommendationEffectRead]) -> dict:
    completed = [effect for effect in reversed(effects) if effect.status == TrainingStatus.completed.value and effect.metrics]
    result = analyze_trend_by_policy(completed)
    return {
        "status": result.status,
        "summary": result.summary,
        "hint": result.hint,
        "evidence": result.evidence,
        "attribution_points": result.attribution_points,
        "reminder_level": result.reminder_level,
        "patient_reminder": result.patient_reminder,
        "family_reminder": result.family_reminder,
        "therapist_reminder": result.therapist_reminder,
    }


def metric_deltas(first: dict[str, float], latest: dict[str, float]) -> dict[str, float]:
    return {
        name: round(latest[name] - first[name], 1)
        for name in PROCESS_METRIC_NAMES
        if name in first and name in latest
    }


def build_trend_evidence(deltas: dict[str, float]) -> list[str]:
    labels = {
        "script_accuracy": ("完整度", "%"),
        "error_count": ("错误", "次"),
        "speech_rate": ("语速", "字/min"),
        "loudness": ("相对响度", "dBFS"),
    }
    points = []
    for key, value in deltas.items():
        label, unit = labels.get(key, (key, ""))
        direction = "提升" if value > 0 else "下降" if value < 0 else "持平"
        points.append(f"{label}{direction} {abs(value):g}{unit}")
    return points or ["暂无可比较指标"]


def speech_rate_better(first: float | None, latest: float | None) -> bool:
    if first is None or latest is None:
        return False
    return abs(latest - 210) + 8 < abs(first - 210)


def loudness_better(first: float | None, latest: float | None) -> bool:
    if first is None or latest is None:
        return False
    return abs(latest - 69) + 3 < abs(first - 69)


def latest_recommendation_review(db: Session, patient_profile_id: UUID) -> TrainingRecommendationReview | None:
    return db.scalar(
        select(TrainingRecommendationReview)
        .where(TrainingRecommendationReview.patient_profile_id == patient_profile_id)
        .order_by(TrainingRecommendationReview.created_at.desc())
    )


def build_recommendation_read(
    db: Session,
    recommended_type: TrainingType,
    headline: str,
    reason: str,
    focus_points: list[str],
    suggested_minutes: int,
    content_level: str,
    autonomy_level: str,
    confidence: float,
    profile_summary: str,
    source: str,
    review_status: str,
    review_id: UUID | None = None,
    therapist_notes: str | None = None,
    updated_at=None,
    adaptation_note: str | None = None,
    reminder: str | None = None,
) -> TrainingRecommendationRead:
    template = pick_template_for_recommendation(
        db,
        recommended_type=recommended_type,
        content_level=content_level,
        autonomy_level=autonomy_level,
    )
    sequence = pick_task_sequence_for_recommendation(
        db,
        recommended_type=recommended_type,
        content_level=content_level,
        autonomy_level=autonomy_level,
    )
    return TrainingRecommendationRead(
        id=review_id,
        recommended_type=recommended_type,
        headline=headline,
        reason=reason,
        focus_points=focus_points,
        suggested_minutes=suggested_minutes,
        content_level=content_level,
        autonomy_level=autonomy_level,
        confidence=confidence,
        profile_summary=profile_summary,
        source=source,
        review_status=review_status,
        therapist_notes=therapist_notes,
        updated_at=updated_at,
        task_template=TaskTemplateRead.model_validate(template) if template else None,
        task_sequence=[TaskTemplateRead.model_validate(item) for item in sequence],
        policy_version=RECOMMENDATION_POLICY["version"],
        adaptation_note=adaptation_note,
        reminder=reminder,
    )


def recommendation_review_to_read(db: Session, review: TrainingRecommendationReview) -> TrainingRecommendationRead:
    return build_recommendation_read(
        db=db,
        recommended_type=review.recommended_type,
        headline=review.headline,
        reason=review.reason,
        focus_points=review.focus_points,
        suggested_minutes=review.suggested_minutes,
        content_level=review.content_level,
        autonomy_level=review.autonomy_level,
        confidence=review.confidence,
        profile_summary=review.profile_summary,
        source="therapist",
        review_status=review.review_status.value,
        review_id=review.id,
        therapist_notes=review.therapist_notes,
        updated_at=review.updated_at,
    )


def decide_recommendation(ability) -> tuple[TrainingType, str, str, list[str], int]:
    accuracy = ability.avg_script_accuracy_recent
    errors = ability.avg_error_count_recent
    speech_rate = ability.avg_speech_rate_recent
    loudness = ability.avg_loudness_recent
    reviewed_count = (ability.evidence or {}).get("reviewed_assessment_count", 0)

    if accuracy is None or errors is None:
        return (
            TrainingType.repeat,
            "先从熟悉短句开始",
            "系统还需要几次训练记录来了解你的表达状态，短句跟读最容易形成稳定反馈。",
            ["把一句话说完整", "不用着急，先听清再开口", "完成后查看系统反馈"],
            8,
        )
    if errors >= 3 or accuracy < 78:
        return (
            TrainingType.repeat,
            "今天先稳住一句话",
            "最近表达里需要留意的地方较多，先练短句能减少负担，也方便看清具体进步。",
            ["慢一点说完整", "重点减少漏字和错字", "每次只关注一个小目标"],
            10,
        )
    if loudness is not None and loudness < -35:
        return (
            TrainingType.repeat,
            "先练声音稳定",
            "最近声音偏轻，跟读训练更适合把气息、音量和句子完整度一起稳住。",
            ["坐直后再开始", "先吸气再说句子", "让声音保持到句尾"],
            10,
        )
    if speech_rate is not None and speech_rate < 180:
        return (
            TrainingType.repeat,
            "练一组连贯短句",
            "最近说话节奏偏慢，可以用熟悉短句练习连续表达，重点减少不必要的停顿。",
            ["一句话尽量连起来", "停顿少一点", "保持清楚比追求快更重要"],
            12,
        )
    if ability.current_content_level in {"L3", "L4", "L5"} and ability.current_autonomy_level in {"S3", "S4"}:
        confidence_note = "治疗师复核已经纳入画像。" if reviewed_count else "当前建议来自系统画像，等待治疗师复核后会更稳。"
        return (
            TrainingType.scenario,
            "可以试试生活场景表达",
            f"最近短句表现比较稳定，适合增加一点自主表达。{confidence_note}",
            ["围绕一个生活场景说清需求", "先说重点，再补充细节", "不用追求很长"],
            12,
        )
    return (
        TrainingType.repeat,
        "继续当前节奏",
        "目前适合保持短句练习，让表达完整度和稳定性继续累积。",
        ["每天完成一小组", "关注反馈里的一个建议", "稳定后再增加场景表达"],
        10,
    )


def pick_template_for_recommendation(
    db: Session,
    recommended_type: TrainingType,
    content_level: str,
    autonomy_level: str,
) -> TaskTemplate | None:
    templates = list(
        db.scalars(
            select(TaskTemplate).where(
                TaskTemplate.task_type == recommended_type,
                TaskTemplate.is_active.is_(True),
            )
        )
    )
    templates = [
        template
        for template in templates
        if not is_generalization_probe(template) and has_functional_scenario_contract(template)
    ]
    if not templates:
        return None
    return min(
        templates,
        key=lambda template: (
            abs(level_number(template.content_level) - level_number(content_level)),
            abs(level_number(template.autonomy_level) - level_number(autonomy_level)),
            -template.recommendation_weight,
            template.created_at,
        ),
    )


def pick_task_sequence_for_recommendation(
    db: Session,
    recommended_type: TrainingType,
    content_level: str,
    autonomy_level: str,
) -> list[TaskTemplate]:
    content = level_number(content_level)
    autonomy = level_number(autonomy_level)
    candidates = [
        template
        for template in
        list(
        db.scalars(
            select(TaskTemplate)
            .where(TaskTemplate.is_active.is_(True))
            .order_by(TaskTemplate.recommendation_weight.desc(), TaskTemplate.created_at.asc())
        )
        )
        if not is_generalization_probe(template) and has_functional_scenario_contract(template)
    ]
    if not candidates:
        return []

    steps = []
    for step in sequence_steps():
        step_type = TrainingType.repeat if step["type"] == "repeat" else recommended_type
        steps.append(
            (
                step["label"],
                step_type,
                max(1, min(5, content + step["content_delta"])),
                max(1, min(4, autonomy + step["autonomy_delta"])),
                bool(step.get("not_easier")),
            )
        )
    selected: list[TaskTemplate] = []
    used_ids = set()
    for _label, step_type, step_content, step_autonomy, not_easier in steps:
        pool = [item for item in candidates if item.task_type == step_type and item.id not in used_ids]
        if not_easier:
            harder_pool = [
                item
                for item in pool
                if level_number(item.content_level) >= content
                and level_number(item.autonomy_level) >= max(1, autonomy - 1)
            ]
            if harder_pool:
                pool = harder_pool
        if not pool:
            pool = [item for item in candidates if item.id not in used_ids]
        if not pool:
            break
        best = min(
            pool,
            key=lambda template: (
                abs(level_number(template.content_level) - step_content),
                abs(level_number(template.autonomy_level) - step_autonomy),
                -template.recommendation_weight,
                template.created_at,
            ),
        )
        selected.append(best)
        used_ids.add(best.id)
    return selected


def level_number(level: str) -> int:
    try:
        return int(level[1:])
    except (TypeError, ValueError):
        return 1


def get_or_create_today_plan(db: Session, user: User) -> TrainingPlan:
    ensure_seed_tasks(db)
    profile = get_patient_profile(db, user)
    plan = db.scalar(
        select(TrainingPlan)
        .where(TrainingPlan.patient_profile_id == profile.id)
        .order_by(TrainingPlan.created_at.desc())
        .options(selectinload(TrainingPlan.items))
    )
    if plan:
        return plan
    plan = TrainingPlan(patient_profile_id=profile.id, title="今日训练")
    db.add(plan)
    db.flush()
    templates = [
        template
        for template in
        list(
        db.scalars(
            select(TaskTemplate)
            .where(TaskTemplate.is_active.is_(True))
            .order_by(TaskTemplate.task_type.asc(), TaskTemplate.content_level.asc(), TaskTemplate.recommendation_weight.desc())
        )
        )
        if not is_generalization_probe(template) and has_functional_scenario_contract(template)
    ]
    for index, template in enumerate(templates):
        db.add(TrainingPlanItem(training_plan_id=plan.id, task_template_id=template.id, order_index=index))
    db.commit()
    return db.scalar(
        select(TrainingPlan).where(TrainingPlan.id == plan.id).options(selectinload(TrainingPlan.items))
    )


def get_today_training(db: Session, user: User) -> TodayTrainingRead:
    plan = get_or_create_today_plan(db, user)
    completed_recommended_sessions = db.scalar(
        select(func.count(TrainingSession.id)).where(
            TrainingSession.training_plan_id == plan.id,
            TrainingSession.recommendation_source.is_not(None),
            TrainingSession.status == TrainingStatus.completed,
        )
    )
    return TodayTrainingRead(
        plan_id=plan.id,
        title=plan.title,
        status=TrainingStatus.completed.value if completed_recommended_sessions else plan.status.value,
        items_count=len(plan.items),
        recommended_completed=bool(completed_recommended_sessions),
        completed_recommended_sessions=completed_recommended_sessions or 0,
    )


def create_session(
    db: Session,
    user: User,
    training_type: TrainingType,
    recommendation_id: UUID | None = None,
    recommendation_source: str | None = None,
    recommendation_headline: str | None = None,
    recommendation_task_ids: list[UUID] | None = None,
    scenario_mode: str = "training",
) -> TrainingSession:
    profile = get_patient_profile(db, user)
    if profile.current_agent_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先创建并选择智能体")
    if scenario_mode not in {"training", "generalization_probe"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未知的场景会话类型")
    if scenario_mode == "generalization_probe" and training_type != TrainingType.scenario:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="泛化探测仅适用于场景表达")
    recommendation = get_training_recommendation(db, user) if recommendation_source else None
    recommended_template = recommendation.task_template if recommendation else None
    recommended_task_ids = recommendation_task_ids or [item.id for item in (recommendation.task_sequence if recommendation else [])]
    plan = get_or_create_today_plan(db, user)
    plan_item = None
    if scenario_mode == "generalization_probe":
        probe = next(
            (
                item
                for item in db.scalars(select(TaskTemplate).where(TaskTemplate.task_type == TrainingType.scenario, TaskTemplate.is_active.is_(True)))
                if is_generalization_probe(item) and has_functional_scenario_contract(item)
            ),
            None,
        )
        if not probe:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="暂时没有可用的泛化探测场景")
        plan_item = next((item for item in plan.items if item.task_template_id == probe.id), None)
        if plan_item is None:
            plan_item = TrainingPlanItem(training_plan_id=plan.id, task_template_id=probe.id, order_index=len(plan.items))
            db.add(plan_item)
            db.flush()
    if (
        plan_item is None
        and recommended_template
        and recommendation
        and recommendation.recommended_type == training_type
        and has_functional_scenario_contract(recommended_template)
    ):
        plan_item = next((item for item in plan.items if item.task_template_id == recommended_template.id), None)
    if plan_item is None:
        plan_item = next(
            (
                item
                for item in plan.items
                if item.task_template.task_type == training_type
                and has_functional_scenario_contract(item.task_template)
                and (scenario_mode == "generalization_probe" or not is_generalization_probe(item.task_template))
            ),
            None,
        )
    if plan_item is None:
        template = next(
            (
                item
                for item in db.scalars(
                    select(TaskTemplate)
                    .where(TaskTemplate.task_type == training_type, TaskTemplate.is_active.is_(True))
                    .order_by(TaskTemplate.recommendation_weight.desc(), TaskTemplate.created_at.asc())
                )
                if not is_generalization_probe(item) and has_functional_scenario_contract(item)
            ),
            None,
        )
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练题不存在")
        plan_item = TrainingPlanItem(training_plan_id=plan.id, task_template_id=template.id, order_index=len(plan.items))
        db.add(plan_item)
        db.flush()
    session = TrainingSession(
        patient_profile_id=profile.id,
        agent_id=profile.current_agent_id,
        training_plan_id=plan.id,
        training_type=training_type,
        recommendation_review_id=recommendation_id,
        recommendation_source=recommendation_source,
        recommendation_snapshot=build_session_recommendation_snapshot(recommendation, recommendation_headline),
        recommendation_matched=bool(recommendation and recommendation.recommended_type == training_type),
    )
    db.add(session)
    db.flush()
    session_plan_items = []
    if recommendation_source and recommended_task_ids:
        for index, task_template_id in enumerate(recommended_task_ids):
            template = db.get(TaskTemplate, task_template_id)
            if not template or not template.is_active or not has_functional_scenario_contract(template):
                continue
            existing_plan_item = next((item for item in plan.items if item.task_template_id == template.id), None)
            if existing_plan_item is None:
                existing_plan_item = TrainingPlanItem(
                    training_plan_id=plan.id,
                    task_template_id=template.id,
                    order_index=len(plan.items) + len(session_plan_items),
                )
                db.add(existing_plan_item)
                db.flush()
            session_plan_items.append(existing_plan_item)
    if not session_plan_items:
        session_plan_items = [plan_item]

    for index, item in enumerate(session_plan_items):
        db.add(
            SessionTask(
                training_session_id=session.id,
                training_plan_item_id=item.id,
                task_template_id=item.task_template_id,
                order_index=index,
            )
        )
    db.commit()
    return get_session(db, user, session.id)


def build_session_recommendation_snapshot(
    recommendation: TrainingRecommendationRead | None,
    recommendation_headline: str | None = None,
) -> dict | None:
    if not recommendation:
        return None
    return {
        "headline": recommendation_headline or recommendation.headline,
        "recommended_type": recommendation.recommended_type.value,
        "source": recommendation.source,
        "review_status": recommendation.review_status,
        "content_level": recommendation.content_level,
        "autonomy_level": recommendation.autonomy_level,
        "confidence": recommendation.confidence,
        "therapist_notes": recommendation.therapist_notes,
        "task_sequence": [str(item.id) for item in recommendation.task_sequence],
    }


def get_session(db: Session, user: User, session_id: UUID) -> TrainingSession:
    profile = get_patient_profile(db, user)
    session = db.scalar(
        select(TrainingSession)
        .where(TrainingSession.id == session_id, TrainingSession.patient_profile_id == profile.id)
        .options(selectinload(TrainingSession.session_tasks).selectinload(SessionTask.task_template))
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练会话不存在")
    return session


def create_avatar_speech(db: Session, user: User, payload: AvatarSpeechCreate) -> AvatarSpeechRead:
    text = payload.text.strip()
    scene = payload.scene.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="数字人口播文本不能为空")
    if len(text) > 150:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="数字人口播文本过长")
    if not scene:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="数字人口播场景不能为空")

    profile = get_patient_profile(db, user)
    if profile.current_agent_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先创建并选择智能体")
    agent = db.get(Agent, profile.current_agent_id)
    if not agent or agent.patient_profile_id != profile.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先创建并选择智能体")

    session = None
    if payload.session_id:
        session = get_session(db, user, payload.session_id)
    if payload.session_task_id:
        task = db.scalar(
            select(SessionTask)
            .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
            .where(SessionTask.id == payload.session_task_id, TrainingSession.patient_profile_id == profile.id)
        )
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练任务不存在")
        if session and task.training_session_id != session.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="训练任务不属于当前会话")

    try:
        provider = get_tts_provider()
    except TTSProviderError as exc:
        log_event("warning", "avatar_speech", "speech_provider_unavailable", error_code=exc.code)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc
    fallback = agent.voice_external_id is None
    if agent.voice_external_id:
        require_active_consent(db, user, agent.id, "voice")
    cache_name = avatar_speech_cache_name(provider.cache_identity(agent.voice_external_id or "default"), text)
    cached_asset = db.scalar(
        select(FileAsset).where(
            FileAsset.owner_user_id == user.id,
            FileAsset.file_type == FileType.generated_audio,
            FileAsset.original_name == cache_name,
            FileAsset.status == FileStatus.active,
        )
    )
    if cached_asset and Path(cached_asset.storage_path).is_file() and Path(cached_asset.storage_path).stat().st_size > 0:
        return AvatarSpeechRead(
            text=text,
            audio_file_id=cached_asset.id,
            audio_url=public_url(cached_asset),
            provider=provider.name,
            fallback=fallback,
            cached=True,
        )
    try:
        audio_path = provider.synthesize(text, agent.voice_external_id or "default")
    except TTSProviderError as exc:
        log_event("warning", "avatar_speech", "speech_generation_failed", error_code=exc.code)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc
    path = Path(audio_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="数字人口播音频生成失败")
    cache_path = path.with_name(cache_name)
    if path != cache_path:
        path.replace(cache_path)
        path = cache_path
    asset = FileAsset(
        owner_user_id=user.id,
        file_type=FileType.generated_audio,
        original_name=path.name,
        storage_path=str(path),
        mime_type="audio/wav",
        size_bytes=path.stat().st_size,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return AvatarSpeechRead(
        text=text,
        audio_file_id=asset.id,
        audio_url=public_url(asset),
        provider=provider.name,
        fallback=fallback,
        cached=False,
    )


def avatar_speech_cache_name(provider_identity: str, text: str) -> str:
    digest = sha256(f"{provider_identity}|{text}".encode("utf-8")).hexdigest()
    return f"avatar_{digest}.wav"


def complete_session_if_needed(db: Session, session: TrainingSession) -> None:
    if all(task.status == TrainingStatus.completed for task in session.session_tasks):
        session.status = TrainingStatus.completed
    db.commit()


def get_patient_profile_by_user_id(db: Session, patient_user_id: UUID) -> PatientProfile:
    patient = db.get(User, patient_user_id)
    if not patient or patient.role != UserRole.patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者不存在")
    profile = db.scalar(select(PatientProfile).where(PatientProfile.user_id == patient.id))
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者档案不存在")
    return profile
