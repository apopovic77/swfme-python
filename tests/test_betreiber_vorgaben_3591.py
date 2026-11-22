"""#3591: keine Vorgabe-Adressen des Betreibers in swfme-python.

Ohne gesetzte Adresse ruft kein Baustein einen Dienst auf: EmitAudit sendet nichts (ein Audit
bricht den Ablauf nie ab), die uebrigen brechen mit einer klaren Meldung ab.
"""

import importlib
import pathlib
import re

import pytest

import swfme

QUELLE = pathlib.Path(swfme.__file__).parent


def test_keine_betreiber_adresse_im_code():
    treffer = []
    for p in QUELLE.rglob("*.py"):
        for nr, zeile in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"arkturian\.com", zeile):
                treffer.append(f"{p.relative_to(QUELLE)}:{nr}")
    assert treffer == []


class _KeinNetz:
    """Ersetzt httpx.AsyncClient: jeder Aufruf ist ein Testfehler."""

    def __init__(self, *a, **k):
        raise AssertionError("ohne Adresse darf kein HTTP-Aufruf entstehen")


@pytest.mark.asyncio
async def test_emit_audit_ohne_basis_sendet_nichts(monkeypatch):
    monkeypatch.delenv("CONTENT_API_BASE", raising=False)
    import swfme.core.atomars.emit_audit as ea
    ea = importlib.reload(ea)
    monkeypatch.setattr(ea.httpx, "AsyncClient", _KeinNetz)
    schritt = ea.EmitAudit(name="Audit")
    schritt.input["message"].value = "Test"
    schritt.input["audit_target"].value = "content_post:1"
    await schritt.execute_impl()
    assert schritt.output["emitted"].value is False


@pytest.mark.asyncio
async def test_store_content_ohne_adresse_bricht_ab(monkeypatch):
    monkeypatch.delenv("CONTENT_API_BASE", raising=False)
    from swfme.processes import data
    monkeypatch.setattr(data.httpx, "AsyncClient", _KeinNetz)
    schritt = data.ProcessStoreContent(name="Speichern")
    schritt.input["title"].value = "t"
    schritt.input["content"].value = "c"
    with pytest.raises(ValueError, match="#3591"):
        await schritt.execute_impl()


@pytest.mark.asyncio
async def test_fetch_content_nimmt_die_umgebung(monkeypatch):
    monkeypatch.setenv("CONTENT_API_BASE", "http://127.0.0.1:9/")
    from swfme.processes import data
    assert data._api_url("") == "http://127.0.0.1:9"
    assert data._api_url("http://andere:1") == "http://andere:1"


def test_agent_session_ohne_adresse_bricht_ab():
    from swfme.agents.session import AgentSession, AgentSessionConfig
    s = AgentSession(AgentSessionConfig(name="x"))
    with pytest.raises(ValueError, match="#3591"):
        s._api_base


@pytest.mark.asyncio
async def test_intervention_ohne_adresse_bricht_ab():
    from swfme.agents.intervention import ProcessAgentIntervention as AgentIntervention
    schritt = AgentIntervention(name="Frage")
    schritt.input["message"].value = "m"
    schritt.input["agent_session"].value = "x"
    with pytest.raises(ValueError, match="#3591"):
        await schritt.execute_impl()
