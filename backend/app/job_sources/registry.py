"""Enabled live job sources from settings."""
from app.core.config import Settings
from app.job_sources.arbeitnow import ArbeitnowAdapter
from app.job_sources.greenhouse import GreenhouseAdapter


def build_adapters(config: Settings) -> list:
    adapters = []
    for name in config.live_job_sources:
        if name == "arbeitnow":
            adapters.append(ArbeitnowAdapter(max_pages=config.ARBEITNOW_MAX_PAGES))
        elif name == "greenhouse":
            adapters.append(GreenhouseAdapter(config.greenhouse_boards))
        else:
            raise ValueError(f"Unknown live job source: {name}")
    return adapters


ATTRIBUTION = {adapter.name: (adapter.attribution, adapter.attribution_url)
               for adapter in (ArbeitnowAdapter(), GreenhouseAdapter([]))}
