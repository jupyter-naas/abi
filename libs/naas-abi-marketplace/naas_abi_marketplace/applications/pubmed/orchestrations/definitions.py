import dagster
from dagster._core.definitions.definitions_class import TJobs, TSensors, TAssets

jobs: TJobs = []
sensors: TSensors = []
assets: TAssets = []

definitions = dagster.Definitions(jobs=jobs, sensors=sensors, assets=assets)
