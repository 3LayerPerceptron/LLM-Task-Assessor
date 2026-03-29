from backend.src.config import settings

import typing as t


if settings.ENVIRONMENT == "test":
    @settings.CELERY.task(name="awwh")
    def awwh() -> bool:
        """A simple Celery task for test successfully complete work."""
        return True

    @settings.CELERY.task(name="oops")
    def oops() -> t.NoReturn:
        """A simple Celery task for test failed working."""
        raise RuntimeError("you know, something wrong happend :(")


celery = settings.CELERY