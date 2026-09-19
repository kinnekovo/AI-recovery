from uuid import UUID
from pydantic import BaseModel,Field
class DatasetCreate(BaseModel): name:str; version:str; description:str|None=None
class SampleAdd(BaseModel): evaluation_run_id:UUID; dimension_code:str
class AnnotationCreate(BaseModel): sample_id:UUID; dimension_code:str; value:float|None=None; unit:str|None=None; comment:str|None=None; annotation_round:int=1
class AdjudicationCreate(AnnotationCreate): pass
class RegistryCreate(BaseModel): metric_code:str; display_name:str; source:str; version:str; dimension_type:str="continuous"; unit:str|None=None
class CalibrationExecute(BaseModel): dataset_id:UUID; metric_code:str; seed:int=17; holdout_ratio:float=.2
