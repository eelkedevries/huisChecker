from huisChecker.contracts import metric_registry
from huisChecker.layers import layer_registry
from huisChecker.report import ReportModuleKey, report_module_registry


def test_every_required_module_is_registered() -> None:
    registered = {c.key for c in report_module_registry.all()}
    for key in ReportModuleKey:
        assert key in registered, f"missing module contract: {key}"


def test_module_metric_and_layer_keys_resolve() -> None:
    for contract in report_module_registry.all():
        for metric_key in contract.metric_keys:
            metric_registry.get(metric_key)  # raises on unknown
        for layer_key in contract.layer_keys:
            layer_registry.get(layer_key)


def test_caveats_sources_module_has_caveat() -> None:
    c = report_module_registry.get(ReportModuleKey.CAVEATS_SOURCES)
    assert c.caveat
