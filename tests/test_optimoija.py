"""Pieni synteettinen skenaario suoraan optimoija-funktiolle, ei
tietokantaa eikä HTTP:tä — varmistaa mallin rakentumisen ja perusrajoitteet."""

from app.models import SopimusTyyppi
from app.services.optimoija import (
    KuskiRow,
    OptimointiParametrit,
    TehtavaRow,
    analysoi_sijoittamattomat,
    koosta_kuskien_yhteenveto,
    ratkaise,
)

KOTI = (0.0, 0.0)
NOUTOPISTE = (0.1, 0.0)
JATTOPISTE = (0.2, 0.0)

AJOAIKA = {
    (KOTI, NOUTOPISTE): (300, 1000.0),
    (NOUTOPISTE, KOTI): (300, 1000.0),
    (KOTI, JATTOPISTE): (600, 2000.0),
    (JATTOPISTE, KOTI): (600, 2000.0),
    (NOUTOPISTE, JATTOPISTE): (300, 1000.0),
    (JATTOPISTE, NOUTOPISTE): (300, 1000.0),
}


def _kuski(paiva_kuski_id: int) -> KuskiRow:
    return KuskiRow(
        paiva_kuski_id=paiva_kuski_id,
        kuski_id=paiva_kuski_id,
        nimi=f"Kuski {paiva_kuski_id}",
        sopimus=SopimusTyyppi.KUUKAUSI,
        tuntihinta=20.0,
        paikkoja=4,
        aloitus=KOTI,
    )


def test_kaksi_tehtavaa_kaksi_kuskia_molemmat_sijoittuvat():
    tehtavat = [
        TehtavaRow(
            id=1, nimi="Tehtava A", mista=NOUTOPISTE, mihin=JATTOPISTE,
            henkiloita=1, perilla_viimeistaan=8 * 60,
        ),
        TehtavaRow(
            id=2, nimi="Tehtava B", mista=NOUTOPISTE, mihin=JATTOPISTE,
            henkiloita=1, perilla_viimeistaan=8 * 60,
        ),
    ]
    kuskit = [_kuski(1), _kuski(2)]
    tulos = ratkaise(tehtavat, kuskit, AJOAIKA, OptimointiParametrit(aikaraja_s=5))

    assert tulos.ratkeaa
    assert tulos.sijoittamatta == []
    assert len(tulos.keikat) == 2


def test_yksin_tehtava_ei_jaa_kyytia_toisen_kanssa():
    tehtavat = [
        TehtavaRow(
            id=1, nimi="Yksinäinen", mista=NOUTOPISTE, mihin=JATTOPISTE,
            henkiloita=1, perilla_viimeistaan=8 * 60, yksin=True,
        ),
        TehtavaRow(
            id=2, nimi="Toinen", mista=NOUTOPISTE, mihin=JATTOPISTE,
            henkiloita=1, perilla_viimeistaan=8 * 60,
        ),
    ]
    kuskit = [_kuski(1), _kuski(2)]
    tulos = ratkaise(tehtavat, kuskit, AJOAIKA, OptimointiParametrit(aikaraja_s=5))

    assert tulos.ratkeaa
    assert tulos.sijoittamatta == []

    # "yksin" tarkoittaa ettei kyytiä jaeta SAMANAIKAISESTI jonkun toisen
    # kanssa — sama auto saa silti ajaa molemmat, kunhan ne eivät mene
    # ajallisesti päällekkäin.
    yksinainen = next(k for k in tulos.keikat if k.tehtava_id == 1)
    toinen = next(k for k in tulos.keikat if k.tehtava_id == 2)
    if yksinainen.paiva_kuski_id == toinen.paiva_kuski_id:
        paallekkain = (
            yksinainen.nouto_min < toinen.jatto_min
            and toinen.nouto_min < yksinainen.jatto_min
        )
        assert not paallekkain


def test_mahdoton_aikaikkuna_paatyy_sijoittamattomiin_syykoodilla():
    mahdoton = TehtavaRow(
        id=99, nimi="Mahdoton", mista=NOUTOPISTE, mihin=JATTOPISTE,
        henkiloita=1, nouto_aikaisintaan=0, nouto_viimeistaan=1,
        perilla_viimeistaan=2,
    )
    kuskit = [_kuski(1)]
    tulos = ratkaise([mahdoton], kuskit, AJOAIKA, OptimointiParametrit(aikaraja_s=5))

    assert tulos.sijoittamatta == [99]

    syyt = analysoi_sijoittamattomat(
        tulos.sijoittamatta, [mahdoton], kuskit, AJOAIKA, OptimointiParametrit(aikaraja_s=5)
    )
    assert syyt[0]["tehtava_id"] == 99
    assert syyt[0]["syy"] == "aikaikkuna"


def test_lukittu_kuski_id_kayttaa_kuski_id_ei_paiva_kuski_id():
    # paiva_kuski_id ja kuski_id ovat TARKOITUKSELLA eri arvoja, jotta testi
    # paljastaisi jos lukitus verrataan väärään id-avaruuteen (regressio:
    # lukittu_kuski_id viittaa kuski.id:hen, ei paiva_kuski.id:hen).
    kuski_a = KuskiRow(
        paiva_kuski_id=101, kuski_id=5, nimi="Kuski A",
        sopimus=SopimusTyyppi.KUUKAUSI, tuntihinta=20.0, paikkoja=4, aloitus=KOTI,
    )
    kuski_b = KuskiRow(
        paiva_kuski_id=102, kuski_id=6, nimi="Kuski B",
        sopimus=SopimusTyyppi.KUUKAUSI, tuntihinta=20.0, paikkoja=4, aloitus=KOTI,
    )
    tehtava = TehtavaRow(
        id=1, nimi="Lukittu tehtävä", mista=NOUTOPISTE, mihin=JATTOPISTE,
        henkiloita=1, perilla_viimeistaan=8 * 60, lukittu_kuski_id=6,
    )
    tulos = ratkaise([tehtava], [kuski_a, kuski_b], AJOAIKA, OptimointiParametrit(aikaraja_s=5))

    assert tulos.sijoittamatta == []
    assert tulos.keikat[0].paiva_kuski_id == 102  # kuski_b (kuski_id=6), ei kuski_a


def test_lukittu_kuski_ei_tarjolla_paatyy_sijoittamattomiin_lukituskonfliktilla():
    kuski_a = KuskiRow(
        paiva_kuski_id=101, kuski_id=5, nimi="Kuski A",
        sopimus=SopimusTyyppi.KUUKAUSI, tuntihinta=20.0, paikkoja=4, aloitus=KOTI,
    )
    tehtava = TehtavaRow(
        id=1, nimi="Lukittu poissaolevalle", mista=NOUTOPISTE, mihin=JATTOPISTE,
        henkiloita=1, perilla_viimeistaan=8 * 60, lukittu_kuski_id=999,
    )
    tulos = ratkaise([tehtava], [kuski_a], AJOAIKA, OptimointiParametrit(aikaraja_s=5))

    assert tulos.ratkeaa
    assert tulos.sijoittamatta == [1]

    syyt = analysoi_sijoittamattomat(
        tulos.sijoittamatta, [tehtava], [kuski_a], AJOAIKA, OptimointiParametrit(aikaraja_s=5)
    )
    assert syyt[0]["syy"] == "lukituskonflikti"


def test_koosta_kuskien_yhteenveto_laskee_kuukausisopimuksen_ilmaiseksi():
    tehtavat = [
        TehtavaRow(
            id=1, nimi="Tehtava A", mista=NOUTOPISTE, mihin=JATTOPISTE,
            henkiloita=1, perilla_viimeistaan=8 * 60,
        ),
    ]
    kuskit = [_kuski(1)]
    tulos = ratkaise(tehtavat, kuskit, AJOAIKA, OptimointiParametrit(aikaraja_s=5))

    yhteenveto = koosta_kuskien_yhteenveto(tulos.keikat, kuskit)
    assert len(yhteenveto) == 1
    assert yhteenveto[0].lisakustannus_eur == 0.0
