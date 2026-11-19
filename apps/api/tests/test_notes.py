from __future__ import annotations

from fastapi.testclient import TestClient

PRIMARY = "INC-2026-0728-001"


def test_note_lifecycle(seeded_client: TestClient) -> None:
    assert seeded_client.get(f"/api/incidents/{PRIMARY}/notes").json() == []

    first = seeded_client.post(
        f"/api/incidents/{PRIMARY}/notes",
        json={
            "text": "Operator confirmed a pallet was moved at 10:30.",
            "author": "arnav",
        },
    )
    assert first.status_code == 201, first.text
    note = first.json()
    assert note["incident_id"] == PRIMARY
    assert note["author"] == "arnav"
    assert note["created_at"]

    second = seeded_client.post(
        f"/api/incidents/{PRIMARY}/notes",
        json={"text": "Linked maintenance ticket MNT-4411."},
    )
    assert second.status_code == 201

    notes = seeded_client.get(f"/api/incidents/{PRIMARY}/notes").json()
    assert [n["text"] for n in notes] == [
        "Operator confirmed a pallet was moved at 10:30.",
        "Linked maintenance ticket MNT-4411.",
    ]

    # Notes ride along with the incident detail.
    detail = seeded_client.get(f"/api/incidents/{PRIMARY}").json()
    assert len(detail["notes"]) == 2

    delete = seeded_client.delete(
        f"/api/incidents/{PRIMARY}/notes/{note['id']}"
    )
    assert delete.status_code == 204
    remaining = seeded_client.get(f"/api/incidents/{PRIMARY}/notes").json()
    assert [n["author"] for n in remaining] == [""]


def test_note_validation_and_404s(seeded_client: TestClient) -> None:
    assert (
        seeded_client.post(
            f"/api/incidents/{PRIMARY}/notes", json={"text": ""}
        ).status_code
        == 422
    )
    assert (
        seeded_client.post(
            "/api/incidents/NOPE/notes", json={"text": "x"}
        ).status_code
        == 404
    )
    assert (
        seeded_client.delete(
            f"/api/incidents/{PRIMARY}/notes/9999"
        ).status_code
        == 404
    )


def test_note_cannot_be_deleted_through_another_incident(
    seeded_client: TestClient,
) -> None:
    note = seeded_client.post(
        f"/api/incidents/{PRIMARY}/notes", json={"text": "mine"}
    ).json()
    # A note id is only addressable under its own incident.
    assert (
        seeded_client.delete(
            f"/api/incidents/INC-2026-0729-002/notes/{note['id']}"
        ).status_code
        == 404
    )


def test_notes_appear_in_the_report(seeded_client: TestClient) -> None:
    seeded_client.post(
        f"/api/incidents/{PRIMARY}/notes",
        json={"text": "Pallet moved by night shift.", "author": "arnav"},
    )
    report = seeded_client.get(f"/api/incidents/{PRIMARY}/report").json()
    assert report["investigation_notes"] == [
        {
            "text": "Pallet moved by night shift.",
            "author": "arnav",
            "created_at": report["investigation_notes"][0]["created_at"],
        }
    ]
    assert "## Investigation notes" in report["markdown"]
    assert "Pallet moved by night shift. — arnav" in report["markdown"]

    # Incidents without notes keep a clean report.
    clean = seeded_client.get(
        "/api/incidents/INC-2026-0730-003/report"
    ).json()
    assert clean["investigation_notes"] == []
    assert "Investigation notes" not in clean["markdown"]
