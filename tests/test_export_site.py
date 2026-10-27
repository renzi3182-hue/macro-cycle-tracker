import re

import pytest

from src.data.cache import DB_PATH
from src.scheduler.export_site import md


def test_md_bold_lists_and_escaping():
    assert md("**Ciao** <b>") == "<p><b>Ciao</b> &lt;b&gt;</p>"
    assert md("- uno\n- **due**") == "<ul><li>uno</li><li><b>due</b></li></ul>"
    assert md("#### Titolo\nriga") == "<h3>Titolo</h3><p>riga</p>"


@pytest.mark.skipif(not DB_PATH.exists(), reason="serve data/cache.db")
def test_every_variant_and_chart_has_its_switch_and_data():
    from src.scheduler.export_site import build

    site = build()
    for name, html in site["pages"].items():
        assert html, name
        switches = set(re.findall(r'data-switch="([^"]+)"', html))
        for cond in re.findall(r'data-when="([^"]+)"', html):
            for part in cond.replace("&amp;", "&").split(";"):
                assert part.split("=")[0] in switches, (name, part)
        for key in re.findall(r'data-chart="([^"]+)"', html):
            assert site["charts"][key.replace("&amp;", "&")]["series"], (name, key)
    assert set(site["stress"]["bases"]) >= {"Basso", "Medio", "Alto"}
