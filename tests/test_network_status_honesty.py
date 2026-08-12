"""Verrous anti-regression sur l'honnetete de la verification reseau.

Chaque test correspond a un defaut reellement constate en v58.
"""

from nms_sim import incidents


def test_unknown_area_never_reports_operational(session):
    """Probleme #4 : une zone non resolue ne doit JAMAIS produire 'operational'."""
    result = incidents.get_network_status(session, "Zoneinexistantexyz")

    assert result["status"] == "area_unknown"
    assert result["verified"] is False
    assert result["status"] != "operational"
    assert result["outages"] == []


def test_empty_area_never_reports_operational(session):
    """Bug C : une zone vide etait traitee comme un reseau sain."""
    result = incidents.get_network_status(session, "")

    assert result["status"] == "area_unknown"
    assert result["verified"] is False
    assert result["reason"] == "no_area_provided"


def test_null_area_outage_does_not_match_every_query(session, make_outage):
    """Bug A : ('' in needle) valait toujours True, donc une panne sans zone
    remontait pour n'importe quelle zone demandee."""
    make_outage(area=None, region=None, area_code=None, resolved=False)

    result = incidents.get_network_status(session, "Tataouine")

    assert result["status"] == "operational"
    assert result["verified"] is True
    assert result["outages"] == []


def test_resolved_area_with_incident_exposes_description(session, make_outage):
    """Probleme #2 : l'agent doit pouvoir expliquer ce qui se passe."""
    make_outage(
        area_code="TN-71-METLAOUI", resolved=False, severity="major",
        cause="fiber_cut", description_fr="Coupure de fibre sur l'axe principal.",
    )

    result = incidents.get_network_status(session, "Metlaouii", "fr")

    assert result["status"] == "incident"
    assert result["verified"] is True
    assert result["match"] == "approximate"
    assert result["outages"][0]["cause"] == "fiber_cut"
    assert "fibre" in result["outages"][0]["description"]


def test_governorate_outage_covers_its_delegations(session, make_outage):
    """Une panne declaree au gouvernorat doit remonter pour ses delegations."""
    make_outage(area_code="TN-12", resolved=False)

    result = incidents.get_network_status(session, "La Soukra")

    assert result["status"] == "incident"
    assert result["area_code"] == "TN-12-SOUKRA"
