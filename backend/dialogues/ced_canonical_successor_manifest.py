"""Frozen authoritative capture manifest for Phase 8 observation replay.

Every entry below was produced by ``capture_canonical_opening_observation``
while the ordinary offline ``CEDOrchestrator._run_registry_phase`` path was
running.  The manifest is the trust anchor that prevents a caller from taking
raw response bytes and relabelling them with a new root/task/provider identity.
"""

from __future__ import annotations

from .ced_canonical_successor_contracts import (
    CanonicalTaskIdentity,
    HistoricalUsageKnowledge,
    ObservationCaptureKind,
    ObservationTransportStatus,
    RecordedCanonicalObservation,
    RecordedHistoricalUsage,
    RecordedObservationProvenance,
)
from .ced_canonical_successor_recording_contracts import (
    CanonicalObservationCaptureReceipt,
    CanonicalRecordedObservationManifest,
    CanonicalRecordedObservationManifestEntry,
)
from .models import AgentRole, DialogPhase, ProviderStatus, TaskKind


CANONICAL_SUCCESSOR_CAPTURE_SOURCE_REVISION = (
    "4a3ad5cd4b3f3db4b86e13e7b4597ab07a0c893d"
)

_ACTION_ID = (
    "szaction_e2f2e183f281d8741db89061d679f535042fc35ff9e25dcfb313a7796e232421"
)
_SOURCE_CONFIGURATION_DIGEST = (
    "46977c180d1484808630ba2693ac522c6cf775dc79406c93926d76468fc95413"
)
_HISTORICAL_USAGE = RecordedHistoricalUsage(
    knowledge=HistoricalUsageKnowledge.PARTIAL,
    model_calls=0,
    tool_calls=0,
    tokens=0,
    cost_microusd=0,
    wall_time_ms=None,
    observation_acquisitions=1,
)


def _entry(
    *,
    capture_receipt_id: str,
    observation_id: str,
    source_capsule_id: str,
    source_execution_id: str,
    source_normalized_semantic_digest: str,
    source_search_state_v1_id: str,
    source_session_semantic_id: str,
    task_identity_id: str,
    agent_id: str,
    task_semantic_digest: str,
    context_digest: str,
    request_semantic_digest: str,
    provider_id: str,
    model_id: str,
    model_config_digest: str,
    provider_status: ProviderStatus,
    raw_text: str,
    raw_output_digest: str,
    source_artifact_id: str,
    source_artifact_digest: str,
    provenance_digest: str,
) -> CanonicalRecordedObservationManifestEntry:
    task = CanonicalTaskIdentity(
        task_identity_id=task_identity_id,
        source_session_semantic_id=source_session_semantic_id,
        phase=DialogPhase.OPENING,
        round_number=0,
        slot_index=0,
        attempt_index=0,
        agent_id=agent_id,
        role=AgentRole.SOCRATES,
        task_kind=TaskKind.SOCRATIC_QUESTION,
        task_semantic_digest=task_semantic_digest,
        context_digest=context_digest,
        request_semantic_digest=request_semantic_digest,
        model_config_digest=model_config_digest,
    )
    provenance = RecordedObservationProvenance(
        capture_kind=ObservationCaptureKind.CANONICAL_RECORDED_TRANSITION,
        source_artifact_id=source_artifact_id,
        source_artifact_digest=source_artifact_digest,
        source_revision=CANONICAL_SUCCESSOR_CAPTURE_SOURCE_REVISION,
        provenance_digest=provenance_digest,
    )
    receipt = CanonicalObservationCaptureReceipt(
        capture_receipt_id=capture_receipt_id,
        source_capsule_id=source_capsule_id,
        source_execution_id=source_execution_id,
        source_configuration_digest=_SOURCE_CONFIGURATION_DIGEST,
        source_normalized_semantic_digest=source_normalized_semantic_digest,
        source_search_state_v1_id=source_search_state_v1_id,
        action_id=_ACTION_ID,
        task_identity=task,
        provider_id=provider_id,
        configured_model_id=model_id,
        actual_model_id=model_id,
        model_config_digest=model_config_digest,
        provider_status=provider_status,
        transport_status=ObservationTransportStatus.DELIVERED,
        raw_output_digest=raw_output_digest,
        historical_usage=_HISTORICAL_USAGE,
        provenance=provenance,
        source_task_id=None,
    )
    observation = RecordedCanonicalObservation(
        observation_id=observation_id,
        capture_receipt_id=capture_receipt_id,
        source_capsule_id=source_capsule_id,
        source_execution_id=source_execution_id,
        source_configuration_digest=_SOURCE_CONFIGURATION_DIGEST,
        source_task_id=None,
        action_id=_ACTION_ID,
        task_identity=task,
        provider_id=provider_id,
        configured_model_id=model_id,
        actual_model_id=model_id,
        model_config_digest=model_config_digest,
        transport_status=ObservationTransportStatus.DELIVERED,
        raw_text=raw_text,
        raw_output_digest=raw_output_digest,
        historical_usage=_HISTORICAL_USAGE,
        provenance=provenance,
    )
    return CanonicalRecordedObservationManifestEntry(
        capture_receipt=receipt,
        observation=observation,
    )


FROZEN_CANONICAL_RECORDED_OBSERVATION_MANIFEST = (
    CanonicalRecordedObservationManifest(
        entries=(
            _entry(
                capture_receipt_id="cedcapture_0533bc778cec56100a695953033e041ba4d6aa52f214c0ec36f3f03f93d28c80",
                observation_id="cedobservation_f48f500d3874bbb9aa537fc0ec7cefc9869397c74d992521847641baffe2c6ec",
                source_capsule_id="cedcapsule_a5499733b7b7561d971034d9d65741b1ab76e32c11abf7651a838ad6be6cbd50",
                source_execution_id="cedexecution_c90d438f2737bcbe3aff9a349412a18671ac88bbf1c4afc743f854b9b09312f6",
                source_normalized_semantic_digest="5af9ecc775a087ff0b20c7c0d80d1c69b8ef1761fee07c0fa9c6f4d61ea8fc02",
                source_search_state_v1_id="szstatev1_a17ce47c27894a3aac4095d0c08da107142a54d2b773c10104fde2b250c2f20e",
                source_session_semantic_id="cedsourcesession_e5516aaecbb7b3f072a35ff5e640e98b490bef09a6fc9254ccbed953fa71a434",
                task_identity_id="cedtasksemantic_b5ace018c4bb1369d62bb5004a99edcd8945e4dd0eef1e206570c96b1d71017a",
                agent_id="phase8-recorded-agent-1",
                task_semantic_digest="1abbf7300703a36a7849a3b6dea82e9ffeb3134295ad68127523b08f714f5898",
                context_digest="c7e105c1b837c31640516f7243e42662c8a377f0be8cc806c6dfb4c6627312f7",
                request_semantic_digest="bcec1aeb613f44c61843979e2469e0b003587650dcc648af39d2b292d1332e93",
                provider_id="phase8-recorded-seat-1",
                model_id="phase8-recorded-model/1",
                model_config_digest="66430933c74f521eb83bb7ee7b115491f2426777927ac5c829c314e4a18283ba",
                provider_status=ProviderStatus.OK,
                raw_text='{"content": {"question": "What assumption makes justified true belief seem sufficient for knowledge, and how do Gettier-style cases challenge that assumption?", "operator": "expose_premise", "epistemic_marker": "open_uncertainty"}, "confidence": 0.7}',
                raw_output_digest="912c229dca5ecb8d0ad0736b5e5241dae6e5a3a6ddf9151e323d1bc321d24f62",
                source_artifact_id="backend/dialogues/ced_canonical_successor_recording_fixtures.py::CanonicalSuccessorRecordingProvider;backend/dialogues/provider_registry.py::ScriptedMockProvider._produce_raw_text",
                source_artifact_digest="100f3cc9ab0996efb1bd385c39fcd99411a2a0f9d6e637d2648027b283ffb9c1",
                provenance_digest="9914ae65ffc4f8d3655f5c705b0ecb3d15466ea69e4c6b1601858c905c36f5b8",
            ),
            _entry(
                capture_receipt_id="cedcapture_da0031c4af533d398ee24fffadac817aa29a587270d674164a0a4e016ee9f19b",
                observation_id="cedobservation_a70f053904c475e5b748812dc4f728b08ce7f6796660964317ea48110bbd9fc9",
                source_capsule_id="cedcapsule_e112a6662752518d4bf07d44e8180488b0b225c93a3318f4287c15969418026c",
                source_execution_id="cedexecution_b8122031348084fed5b62c5fe236e1382f934879f1a8e34d0663a61fc7288e66",
                source_normalized_semantic_digest="2468f4e78252ab19e1821ab6d4cdd35619527d006260cd919a72cc337b399710",
                source_search_state_v1_id="szstatev1_4ca771da49e8be794d69f4eb11b8c811260107c024d1b0b245023f724d12f7fe",
                source_session_semantic_id="cedsourcesession_1865a7e881dddb905b6e4d98a716b6ced6f009f601f8cf00f1ed06025cd0cae3",
                task_identity_id="cedtasksemantic_dbbbda790ce50da217457ad6b4c325f77846d88df8f0c29ff616ff80792e628d",
                agent_id="phase8-recorded-agent-0",
                task_semantic_digest="1dc32e986118ede060df30390e37fc309bb046a2faa84c106417a87681f577a6",
                context_digest="c7e105c1b837c31640516f7243e42662c8a377f0be8cc806c6dfb4c6627312f7",
                request_semantic_digest="01087e3506613fac89e4e1ab4905293f7ec54518bf723d070f8b8e67077761d8",
                provider_id="phase8-recorded-seat-0",
                model_id="phase8-recorded-model/0",
                model_config_digest="b50ca0e89d226cd44b67731715c2919eac1861b513fd3b67127662ab2249e845",
                provider_status=ProviderStatus.OK,
                raw_text='{"content": {"question": "", "operator": "clarify", "epistemic_marker": "open_uncertainty"}, "confidence": 0.7}',
                raw_output_digest="9f092460d0839f71f11cb8ef55a3f33f43390f1874d044088e28b497611aefe9",
                source_artifact_id="backend/dialogues/ced_canonical_successor_recording_fixtures.py::CanonicalSuccessorRecordingProvider;tests_dialogues/test_socratic_acceptance_contract.py::EmptySocrates._produce_raw_text",
                source_artifact_digest="7b9f2af0f8acb498aa7641ffaf2818ef9b608dbedbe2aa61b7483aa5ef9d697a",
                provenance_digest="90cf5017cdca6679a7287729dfff74d80a7d5fa75f52c49cc43559e075488a35",
            ),
            _entry(
                capture_receipt_id="cedcapture_ab1938fa95e2e37c4a6095c62babd4176619aa8b881476af868358703ef4c41a",
                observation_id="cedobservation_bffdacf2e34b4526ea1b65758f89337fa7e71c7c33ffe5005d8686c9a177d8db",
                source_capsule_id="cedcapsule_25bdd8370dda28f17aa4943bfe8db092fdff3457029e42927e0375f4c9d4be2f",
                source_execution_id="cedexecution_5ddf5c0cadd96f843e322746208c5a4143b94d725a2cba5a5b16e1299f6f0386",
                source_normalized_semantic_digest="57467024f1d5cfac788bb3e45ffda15bf8cfdf5103ec610737ceeda7aa6c96b5",
                source_search_state_v1_id="szstatev1_62768b6d0e6add1922c9b8b6ab0c0e445d64c38e3c621cff854d5aad35ffe57f",
                source_session_semantic_id="cedsourcesession_4caeb8a414901ae159e899ec7f5eebb483b299ff4157d901f9e93662515caa11",
                task_identity_id="cedtasksemantic_a5b750f75bbe7a273e8ddc4f2bd195c2b3e27bc16a20ef9940fe42148897ae0a",
                agent_id="phase8-recorded-agent-0",
                task_semantic_digest="29ede9e4bb5ec48bcf76ae3890f10e8cd3d094f27be6fd688ad5421a3248ad9c",
                context_digest="a967affed98c5005207b9fc0767c87b219d7e7114e9b8912da979ebd40bf497e",
                request_semantic_digest="53f471f624d1639460791b042e0a4f6720fc8ea2866b597c91aa4aecc72c7ed6",
                provider_id="phase8-recorded-seat-0",
                model_id="phase8-recorded-model/0",
                model_config_digest="b50ca0e89d226cd44b67731715c2919eac1861b513fd3b67127662ab2249e845",
                provider_status=ProviderStatus.OK,
                raw_text='{"content": {"question": "Could the order be Clara, Anna, Elena, David, Farid, Ben?", "operator": "draw_consequence", "grounded_in": [], "introduces_new_proposition": false, "inquiry_state": "continue_inquiry", "epistemic_marker": "reasonable_hypothesis"}, "confidence": 0.6}',
                raw_output_digest="62e1cd3fe301b49bdb114882ec581fe3b86ea829b2b0e273854cb7fca7b3664a",
                source_artifact_id="backend/dialogues/ced_canonical_successor_recording_fixtures.py::CanonicalSuccessorRecordingProvider;tests_dialogues/test_socratic_firewall.py::Injecting._produce_raw_text",
                source_artifact_digest="bb68e92514a9a388fac4d588bd6e21ddfaec8dda1ee34541b7b3d9076d68a5f6",
                provenance_digest="78c31bd829883e560e7af581f01f68622448319ce074126af92c6ab7d44f1f53",
            ),
            _entry(
                capture_receipt_id="cedcapture_20f0f52e08bef675f27b8aeaabdf28e32384a5c579565df830dc6800a73abcb3",
                observation_id="cedobservation_2acba7af2deaea8a40bde110ca2d94f04ef540bd7250ca39902bd61114e729f3",
                source_capsule_id="cedcapsule_cd793e145d3f4c7cee1da40a3c2dcd8d63e6c6e51bb17381e5128c8990160df4",
                source_execution_id="cedexecution_a2fd4b7277aec1b489d246b9e0d6a68c06384dd7a17055b78b9ffb31969093d5",
                source_normalized_semantic_digest="3d1deb4b6316f466d3ddbea340c9ad46911deb9bf034564a5f7185ba3a4254cd",
                source_search_state_v1_id="szstatev1_d604e5dd40cc2de821ad6fe236fbc32a59d330bdda794f1ea0124a46c6010446",
                source_session_semantic_id="cedsourcesession_6b41f2afe5123786a414e91b81f5e3d5a142dc0a66f7935afd4950699fea05ab",
                task_identity_id="cedtasksemantic_c7e220c184714b8d960f90aaa94bb96d7c89350fe08394a67d6e64bcb272a47c",
                agent_id="phase8-recorded-agent-1",
                task_semantic_digest="37ee909044127cdd76b77df3ed8099c5498c2bb580fb9e25371491671a880774",
                context_digest="c7e105c1b837c31640516f7243e42662c8a377f0be8cc806c6dfb4c6627312f7",
                request_semantic_digest="8df788475297d9bb0cf69a1f8e57294ee1fe9544e9eb12a8fc2574a3e838d266",
                provider_id="phase8-recorded-seat-1",
                model_id="phase8-recorded-model/1",
                model_config_digest="66430933c74f521eb83bb7ee7b115491f2426777927ac5c829c314e4a18283ba",
                provider_status=ProviderStatus.INVALID_JSON,
                raw_text="<<< this is not valid json >>>",
                raw_output_digest="a32f8c0679ca2b86616b554deb6a700098d8bd5332e07cc404c73f746bedd91f",
                source_artifact_id="backend/dialogues/ced_canonical_successor_recording_fixtures.py::CanonicalSuccessorRecordingProvider;backend/dialogues/provider_registry.py::InvalidJSONProvider._produce_raw_text",
                source_artifact_digest="50edcf037b938f2fdeb51075751c48319e90b87e135073287cc3b10cfec3e1c8",
                provenance_digest="8cb3f04f9214b66ca8540ca8c4086b1884c807b66b3cc84ed38612d949dde297",
            ),
            _entry(
                capture_receipt_id="cedcapture_949b1b3ba7446437fc118c48788a090518d9d9fb405c0e4a281e1edd70a6a58c",
                observation_id="cedobservation_c0f920e8f25f78f4b05ad821f62acc23583c19d4ce2204473c9b214bdae12ab3",
                source_capsule_id="cedcapsule_1663e9cdc514b6c26122199e95a6eb3dd484871c183cfd5e1763621090c6a3a5",
                source_execution_id="cedexecution_b90283c74cad0cbe7ed80eefe62e6e5f121f894c150eb9f79b0458c9c88bd293",
                source_normalized_semantic_digest="fc9f55de4b2bb880e2e282fedd4e20b0677dd3cd44ee6a63b2c4c0de74176924",
                source_search_state_v1_id="szstatev1_27c2557d004139243424f6ffc2c8d7326a1ee94d9f550cf2101e2cf5b2446466",
                source_session_semantic_id="cedsourcesession_4a3e07e76753b1cb754e6ba16989023ad73b34af3adfd67304b214f280f524b1",
                task_identity_id="cedtasksemantic_961ea87b04998a20389d196bb76d2ece700faa8d45c75cdd2361648f8f8ea2d4",
                agent_id="phase8-recorded-agent-0",
                task_semantic_digest="7d9e907db1eaf201d17068645c624ec51450ec4f60d63d7dc38129948b94914f",
                context_digest="c7e105c1b837c31640516f7243e42662c8a377f0be8cc806c6dfb4c6627312f7",
                request_semantic_digest="8df788475297d9bb0cf69a1f8e57294ee1fe9544e9eb12a8fc2574a3e838d266",
                provider_id="phase8-recorded-seat-0",
                model_id="phase8-recorded-model/0",
                model_config_digest="b50ca0e89d226cd44b67731715c2919eac1861b513fd3b67127662ab2249e845",
                provider_status=ProviderStatus.SCHEMA_ERROR,
                raw_text='{"content": "should-be-a-dict", "confidence": 0.7}',
                raw_output_digest="ebc67fd048f0e68bb50eb48a1bfdd61b45f4aeb9586c5a76a6e0543ca9f82021",
                source_artifact_id="backend/dialogues/ced_canonical_successor_recording_fixtures.py::CanonicalSuccessorRecordingProvider;backend/dialogues/provider_registry.py::SchemaErrorProvider._produce_raw_text",
                source_artifact_digest="ad756f10b1c1eaa0d53777e0d70c27fa2829a5f58c30cf07f7a550b45b1b08c5",
                provenance_digest="0ed02fa8109b45c68d88481e1a78e40a5fd408512d3299cf5b2d0d34ba628ef9",
            ),
        )
    )
)


def verify_authoritative_recorded_observation(
    observation: RecordedCanonicalObservation,
) -> bool:
    """Return true only for exact bytes already anchored in the frozen manifest."""

    try:
        entry = FROZEN_CANONICAL_RECORDED_OBSERVATION_MANIFEST.entry_for_receipt(
            observation.capture_receipt_id
        )
    except KeyError:
        return False
    return observation == entry.observation


__all__ = [
    "CANONICAL_SUCCESSOR_CAPTURE_SOURCE_REVISION",
    "FROZEN_CANONICAL_RECORDED_OBSERVATION_MANIFEST",
    "verify_authoritative_recorded_observation",
]
