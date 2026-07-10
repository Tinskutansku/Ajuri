import pytest

from app.models import SopimusTyyppi
from app.services.kustannus import lisakustannus_eur

TUNTIHINTA = 20.0


def test_kuukausi_alle_8h_on_ilmainen():
    assert lisakustannus_eur(SopimusTyyppi.KUUKAUSI, 7 * 60, TUNTIHINTA) == 0.0


def test_kuukausi_ylityo_8_10h():
    # 9h -> 1h ylityötä x1.5
    odotettu = 1 * TUNTIHINTA * 1.5
    assert lisakustannus_eur(SopimusTyyppi.KUUKAUSI, 9 * 60, TUNTIHINTA) == pytest.approx(odotettu)


def test_kuukausi_ylityo_yli_10h():
    # 11h -> 2h x1.5 + 1h x2.0
    odotettu = 2 * TUNTIHINTA * 1.5 + 1 * TUNTIHINTA * 2.0
    assert lisakustannus_eur(SopimusTyyppi.KUUKAUSI, 11 * 60, TUNTIHINTA) == pytest.approx(odotettu)


def test_paiva_on_aina_8h_hinta_kun_kaytossa():
    odotettu = 8 * TUNTIHINTA
    assert lisakustannus_eur(SopimusTyyppi.PAIVA, 3 * 60, TUNTIHINTA) == pytest.approx(odotettu)


def test_paiva_ei_kaytossa_on_ilmainen():
    assert lisakustannus_eur(SopimusTyyppi.PAIVA, 0, TUNTIHINTA) == 0.0


def test_paiva_ylityo_paalle_8h_hinnan():
    odotettu = 8 * TUNTIHINTA + 1 * TUNTIHINTA * 1.5
    assert lisakustannus_eur(SopimusTyyppi.PAIVA, 9 * 60, TUNTIHINTA) == pytest.approx(odotettu)


def test_tunti_alle_minimin_veloittaa_4h():
    odotettu = 4 * TUNTIHINTA
    assert lisakustannus_eur(SopimusTyyppi.TUNTI, 2 * 60, TUNTIHINTA) == pytest.approx(odotettu)


def test_tunti_yli_minimin_veloittaa_toteuman():
    odotettu = 6 * TUNTIHINTA
    assert lisakustannus_eur(SopimusTyyppi.TUNTI, 6 * 60, TUNTIHINTA) == pytest.approx(odotettu)


def test_tunti_ylityo_8_10h():
    odotettu = 8 * TUNTIHINTA + 1 * TUNTIHINTA * 1.5
    assert lisakustannus_eur(SopimusTyyppi.TUNTI, 9 * 60, TUNTIHINTA) == pytest.approx(odotettu)
