"""ÖBB-HAFAS-Profil für pyhafas (Community-Profil, lokal eingebunden)."""

import pytz

from pyhafas.profile.base import BaseProfile

from services.hafas_oebb.requests.journey import OEBBJourneyRequest
from services.hafas_oebb.requests.journeys import OEBBJourneysRequest


class OEBBProfile(OEBBJourneyRequest, OEBBJourneysRequest, BaseProfile):
    """HaFAS-Profil der Österreichischen Bundesbahnen (ÖBB)."""

    baseUrl = "https://fahrplan.oebb.at/bin/mgate.exe"

    locale = "de-AT"
    timezone = pytz.timezone("Europe/Vienna")

    requestBody = {
        "client": {
            "id": "OEBB",
            "v": "6030600",
            "type": "IPH",
            "name": "oebbPROD-ADHOC",
        },
        "ext": "OEBB.13",
        "lang": "deu",
        "ver": "1.45",
        "auth": {"type": "AID", "aid": "OWDL4fE4ixNiPBBm"},
    }

    availableProducts = {
        "highspeed": [1],
        "eurocity-intercity": [2, 4],
        "durchgang-euronight": [8, 4096],
        "regional": [16],
        "s-bahn": [32],
        "bus": [64],
        "ferry": [128],
        "u-bahn": [256],
        "tram": [512],
        "on-call": [2048],
    }

    defaultProducts = [
        "highspeed",
        "eurocity-intercity",
        "durchgang-euronight",
        "regional",
        "s-bahn",
        "bus",
        "ferry",
        "u-bahn",
        "tram",
        "on-call",
    ]
