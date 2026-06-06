from typing import List

from pyhafas.profile.base import BaseJourneysRequest
from pyhafas.profile.interfaces.requests.journeys import JourneysRequestInterface
from pyhafas.types.fptf import Journey
from pyhafas.types.hafas_response import HafasResponse


class OEBBJourneysRequest(BaseJourneysRequest, JourneysRequestInterface):
    """ÖBB-Journeys-Parser (Journey-ID liegt unter jny['recon']['ctx'])."""

    def parse_journeys_request(self, data: HafasResponse) -> List[Journey]:
        journeys = []

        for jny in data.res["outConL"]:
            date = self.parse_date(jny["date"])
            journeys.append(
                Journey(
                    jny["recon"]["ctx"],
                    date=date,
                    duration=self.parse_timedelta(jny["dur"]),
                    legs=self.parse_legs(jny, data.common, date),
                )
            )
        return journeys
