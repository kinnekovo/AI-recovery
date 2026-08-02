<template>
  <section class="page-stack">
    <div class="page-heading">
      <span class="kicker">进入训练</span>
      <h1>选择一次训练类型</h1>
      <p>第一阶段提供跟读训练和场景表达训练，评分由后端 Mock 服务返回。</p>
    </div>
    <div class="training-choice">
      <RouterLink class="choice-panel" to="/training/repeat">
        <strong>跟读训练</strong>
        <p>系统展示目标句子，患者录音跟读，适合练习清晰度、流畅度和音量。</p>
      </RouterLink>
      <RouterLink class="choice-panel" to="/training/scenario">
        <strong>场景表达</strong>
        <p>围绕生活场景自由表达，适合练习内容组织和自主表达。</p>
      </RouterLink>
    </div>
  </section>
</template>
