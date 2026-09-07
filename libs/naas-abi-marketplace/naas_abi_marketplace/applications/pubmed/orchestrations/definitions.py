import dagster
from dagster._core.definitions.definitions_class import TAssets, TJobs, TSensors

jobs : TJobs = []
sensors : TSensors = []
assets : TAssets = []

definitions = dagster.Definitions(jobs=jobs, sensors=sensors, assets=assets)