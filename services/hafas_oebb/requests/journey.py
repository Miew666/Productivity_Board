from pyhafas.profile import ProfileInterface
from pyhafas.profile.base import BaseJourneyRequest
from pyhafas.profile.interfaces.requests.journey import JourneyRequestInterface
from pyhafas.types.fptf import Journey
from pyhafas.types.hafas_response import HafasResponse


class OEBBJourneyRequest(BaseJourneyRequest, JourneyRequestInterface):
    """ÖBB-Journey-Refresh-Parser."""

    def format_journey_request(self: ProfileInterface, journey: Journey) -> dict:
        return {"req": {"outReconL": [{"ctx": journey.id}]}, "meth": "Reconstruction"}

    def parse_journey_request(self: ProfileInterface, data: HafasResponse) -> Journey:
        date = self.parse_date(data.res["outConL"][0]["date"])
        return Journey(
            data.res["outConL"][0]["recon"]["ctx"],
            date=date,
            duration=self.parse_timedelta(data.res["outConL"][0]["dur"]),
            legs=self.parse_legs(data.res["outConL"][0], data.common, date),
        )
