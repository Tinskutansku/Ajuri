"""Ajolistan optimointi OR-Toolsilla (docs/optimoija-spec.md).

Pohjana `ajolista_optimoija.py`-prototyyppi, mutta syöte tulee
tietokannasta kovakoodatun testidatan sijaan: solmugraafi rakennetaan
`TehtavaRow`/`KuskiRow`-riveistä ja ajoajat haetaan valmiiksi lasketusta
matriisista (ks. `matka_cache.py`).

Hakua ohjaava kustannusmalli (fixed cost, span cost coefficient) on
tarkoituksella karkeampi kuin `kustannus.lisakustannus_eur` — se vain
ohjaa OR-Toolsia oikeaan suuntaan, tarkka € lasketaan ratkaisun jälkeen.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.models import SopimusTyyppi
from app.services.kustannus import lisakustannus_eur

Piste = tuple[float, float]
AjoaikaMatriisi = dict[tuple[Piste, Piste], tuple[int, float]]

RUUHKA_ALKU_MIN = 6 * 60
RUUHKA_LOPPU_MIN = 9 * 60
RUUHKA_KERROIN = 1.2
MAX_VUORO_MIN = 13 * 60
SOFT_BOUND_8H_MIN = 8 * 60
SOFT_BOUND_10H_MIN = 10 * 60
STABILITEETTI_SAKKO_SNT = 500  # 5 € — pieni sakko tehtävän kuskin vaihtumisesta reoptimoinnissa


@dataclass
class OptimointiParametrit:
    aikaraja_s: int = 15
    max_etuajassa_min: int = 30
    max_kyytiaika_lisa_min: int = 25


@dataclass
class TehtavaRow:
    id: int
    nimi: str
    mista: Piste
    mihin: Piste
    henkiloita: int
    nouto_aikaisintaan: int | None = None
    nouto_viimeistaan: int | None = None
    perilla_aikaisintaan: int | None = None
    perilla_viimeistaan: int | None = None
    lukittu_kuski_id: int | None = None
    yksin: bool = False
    edellinen_paiva_kuski_id: int | None = None  # reoptimoinnin stabiliteettisakkoa varten


@dataclass
class KuskiRow:
    paiva_kuski_id: int
    nimi: str
    sopimus: SopimusTyyppi
    tuntihinta: float
    paikkoja: int
    aloitus: Piste
    vuoro_aikaisintaan: int | None = None
    vuoro_viimeistaan: int | None = None
    aloitus_aika_min: int | None = None  # reoptimoinnissa: viimeisen lukitun keikan jättöaika


@dataclass
class KeikkaTulos:
    tehtava_id: int
    paiva_kuski_id: int
    nouto_min: int
    jatto_min: int
    lukittu: bool = False


@dataclass
class OptimointiTulos:
    keikat: list[KeikkaTulos] = field(default_factory=list)
    sijoittamatta: list[int] = field(default_factory=list)
    ratkeaa: bool = True


@dataclass
class KuskinYhteenveto:
    paiva_kuski_id: int
    alku_min: int
    loppu_min: int
    kesto_min: int
    lisakustannus_eur: float
    keikat: list[KeikkaTulos]


def _sopimus_kustannusparametrit(sopimus: SopimusTyyppi, tuntihinta: float) -> tuple[int, int]:
    """(fixed_cost_snt, span_cost_coefficient_snt_per_min) hakua ohjaavaan
    malliin. Ei tarkka €, ks. moduulin docstring."""
    c_min = round(tuntihinta / 60 * 100)
    if sopimus == SopimusTyyppi.KUUKAUSI:
        return 0, 1  # 0-8h jo maksettu -> vain pieni tie-breaker
    if sopimus == SopimusTyyppi.PAIVA:
        return round(8 * tuntihinta * 100), c_min
    if sopimus == SopimusTyyppi.TUNTI:
        return round(4 * tuntihinta * 100), c_min
    raise ValueError(f"Tuntematon sopimustyyppi: {sopimus}")


def ratkaise(
    tehtavat: list[TehtavaRow],
    kuskit: list[KuskiRow],
    ajoaika: AjoaikaMatriisi,
    parametrit: OptimointiParametrit,
) -> OptimointiTulos:
    if not tehtavat:
        return OptimointiTulos(ratkeaa=True)
    if not kuskit:
        return OptimointiTulos(sijoittamatta=[t.id for t in tehtavat], ratkeaa=True)

    T = len(tehtavat)
    n_kuskia = len(kuskit)
    n_nodes = 2 * T + 2 * n_kuskia

    def node_paikka(node: int) -> Piste:
        if node < T:
            return tehtavat[node].mista
        if node < 2 * T:
            return tehtavat[node - T].mihin
        k = (node - 2 * T) // 2
        return kuskit[k].aloitus

    def on_end(node: int) -> bool:
        return node >= 2 * T and (node - 2 * T) % 2 == 1

    starts = [2 * T + 2 * k for k in range(n_kuskia)]
    ends = [2 * T + 2 * k + 1 for k in range(n_kuskia)]

    manager = pywrapcp.RoutingIndexManager(n_nodes, n_kuskia, starts, ends)
    routing = pywrapcp.RoutingModel(manager)

    def ajoaika_min(a: Piste, b: Piste) -> int:
        """Time-dimensio on minuutteina (kuten Tehtava-taulun kellonajat),
        mutta Matka-välimuisti/reititys-API palauttaa ajoaika_s sekunteina."""
        if a == b:
            return 0
        return round(ajoaika[(a, b)][0] / 60)

    def transit_cb(from_i, to_i):
        f, to = manager.IndexToNode(from_i), manager.IndexToNode(to_i)
        if on_end(to):
            return 0
        kesto = ajoaika_min(node_paikka(f), node_paikka(to))
        if to < T:
            teht = tehtavat[to]
            alku = teht.nouto_aikaisintaan if teht.nouto_aikaisintaan is not None else 5 * 60
            if RUUHKA_ALKU_MIN <= alku < RUUHKA_LOPPU_MIN:
                kesto = round(kesto * RUUHKA_KERROIN)
        return kesto

    transit_idx = routing.RegisterTransitCallback(transit_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    routing.AddDimension(transit_idx, 24 * 60, 30 * 60, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")

    for i, teht in enumerate(tehtavat):
        pick = manager.NodeToIndex(i)
        drop = manager.NodeToIndex(i + T)
        alku = teht.nouto_aikaisintaan if teht.nouto_aikaisintaan is not None else 5 * 60
        loppu = teht.nouto_viimeistaan if teht.nouto_viimeistaan is not None else 26 * 60
        time_dim.CumulVar(pick).SetRange(alku, loppu)
        if teht.perilla_viimeistaan is not None:
            aik = (
                teht.perilla_aikaisintaan
                if teht.perilla_aikaisintaan is not None
                else teht.perilla_viimeistaan - parametrit.max_etuajassa_min
            )
            time_dim.CumulVar(drop).SetRange(aik, teht.perilla_viimeistaan)

    solver = routing.solver()
    for i, teht in enumerate(tehtavat):
        pick = manager.NodeToIndex(i)
        drop = manager.NodeToIndex(i + T)
        routing.AddPickupAndDelivery(pick, drop)
        solver.Add(routing.VehicleVar(pick) == routing.VehicleVar(drop))
        solver.Add(time_dim.CumulVar(pick) <= time_dim.CumulVar(drop))
        if teht.henkiloita > 0:
            suora = ajoaika_min(teht.mista, teht.mihin)
            solver.Add(
                time_dim.CumulVar(drop) - time_dim.CumulVar(pick)
                <= suora + parametrit.max_kyytiaika_lisa_min
            )
        routing.AddDisjunction([pick], 1_000_000)
        routing.AddDisjunction([drop], 1_000_000)

        if teht.lukittu_kuski_id is not None:
            sallitut = [
                v for v, k in enumerate(kuskit) if k.paiva_kuski_id == teht.lukittu_kuski_id
            ]
            routing.SetAllowedVehiclesForIndex(sallitut, pick)
            routing.SetAllowedVehiclesForIndex(sallitut, drop)

        if teht.edellinen_paiva_kuski_id is not None:
            vastaavat = [
                v for v, k in enumerate(kuskit) if k.paiva_kuski_id == teht.edellinen_paiva_kuski_id
            ]
            if vastaavat:
                routing.AddSoftSameVehicleConstraint(
                    [routing.Start(vastaavat[0]), pick], STABILITEETTI_SAKKO_SNT
                )

    # --- Kapasiteetti: per-ajoneuvo kysyntä, "yksin" täyttää koko auton ---
    capacities = [k.paikkoja for k in kuskit]

    def tee_kysynta_cb(v: int):
        def cb(from_i):
            node = manager.IndexToNode(from_i)
            if node < T:
                teht = tehtavat[node]
                return capacities[v] if teht.yksin else teht.henkiloita
            if node < 2 * T:
                teht = tehtavat[node - T]
                return -capacities[v] if teht.yksin else -teht.henkiloita
            return 0

        return cb

    kysynta_indeksit = [
        routing.RegisterUnaryTransitCallback(tee_kysynta_cb(v)) for v in range(n_kuskia)
    ]
    routing.AddDimensionWithVehicleTransitAndCapacity(
        kysynta_indeksit, 0, capacities, True, "Seats"
    )

    # --- Kustannusmalli (hakua ohjaava) + vuororajoitteet per ajoneuvo ---
    for v, k in enumerate(kuskit):
        fixed_snt, span_snt = _sopimus_kustannusparametrit(k.sopimus, k.tuntihinta)
        routing.SetFixedCostOfVehicle(fixed_snt, v)
        time_dim.SetSpanCostCoefficientForVehicle(span_snt, v)
        time_dim.SetSpanUpperBoundForVehicle(MAX_VUORO_MIN, v)
        time_dim.SetSoftSpanUpperBoundForVehicle(
            pywrapcp.BoundCost(SOFT_BOUND_8H_MIN, max(span_snt // 2, 1)), v
        )
        time_dim.SetQuadraticCostSoftSpanUpperBoundForVehicle(
            pywrapcp.BoundCost(SOFT_BOUND_10H_MIN, 2), v
        )
        routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(routing.End(v)))
        routing.AddVariableMaximizedByFinalizer(time_dim.CumulVar(routing.Start(v)))

        alku_idx = routing.Start(v)
        loppu_idx = routing.End(v)
        if k.aloitus_aika_min is not None:
            time_dim.CumulVar(alku_idx).SetRange(k.aloitus_aika_min, k.aloitus_aika_min)
        elif k.vuoro_aikaisintaan is not None:
            time_dim.CumulVar(alku_idx).SetMin(k.vuoro_aikaisintaan)
        if k.vuoro_viimeistaan is not None:
            time_dim.CumulVar(loppu_idx).SetMax(k.vuoro_viimeistaan)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    )
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    params.time_limit.FromSeconds(parametrit.aikaraja_s)

    sol = routing.SolveWithParameters(params)
    if sol is None:
        return OptimointiTulos(sijoittamatta=[t.id for t in tehtavat], ratkeaa=False)

    sijoittamatta = [
        teht.id for i, teht in enumerate(tehtavat) if not sol.Value(routing.ActiveVar(manager.NodeToIndex(i)))
    ]

    keikat: list[KeikkaTulos] = []
    for v, k in enumerate(kuskit):
        idx = routing.Start(v)
        while not routing.IsEnd(idx):
            node = manager.IndexToNode(idx)
            if node < T:
                teht = tehtavat[node]
                drop_idx = manager.NodeToIndex(node + T)
                keikat.append(
                    KeikkaTulos(
                        tehtava_id=teht.id,
                        paiva_kuski_id=k.paiva_kuski_id,
                        nouto_min=sol.Value(time_dim.CumulVar(idx)),
                        jatto_min=sol.Value(time_dim.CumulVar(drop_idx)),
                        lukittu=False,
                    )
                )
            idx = sol.Value(routing.NextVar(idx))

    return OptimointiTulos(keikat=keikat, sijoittamatta=sijoittamatta, ratkeaa=True)


def koosta_kuskien_yhteenveto(
    keikat: list[KeikkaTulos], kuskit: list[KuskiRow]
) -> list[KuskinYhteenveto]:
    """Ryhmittelee keikat kuskeittain ja laskee tarkan päivän lisäkustannuksen
    (koko päivä — lukitut + uudet keikat yhdessä)."""
    kuski_by_id = {k.paiva_kuski_id: k for k in kuskit}
    per_kuski: dict[int, list[KeikkaTulos]] = {}
    for keikka in keikat:
        per_kuski.setdefault(keikka.paiva_kuski_id, []).append(keikka)

    yhteenvedot = []
    for paiva_kuski_id, omat in per_kuski.items():
        k = kuski_by_id[paiva_kuski_id]
        alku = min(kk.nouto_min for kk in omat)
        loppu = max(kk.jatto_min for kk in omat)
        kesto = loppu - alku
        yhteenvedot.append(
            KuskinYhteenveto(
                paiva_kuski_id=paiva_kuski_id,
                alku_min=alku,
                loppu_min=loppu,
                kesto_min=kesto,
                lisakustannus_eur=round(lisakustannus_eur(k.sopimus, kesto, k.tuntihinta), 2),
                keikat=sorted(omat, key=lambda kk: kk.nouto_min),
            )
        )
    return yhteenvedot


def _selvita_syy(
    teht: TehtavaRow,
    kuskit: list[KuskiRow],
    ajoaika: AjoaikaMatriisi,
    parametrit: OptimointiParametrit,
) -> tuple[str, str]:
    if teht.lukittu_kuski_id is not None:
        kandidaatit = [k for k in kuskit if k.paiva_kuski_id == teht.lukittu_kuski_id]
        if not kandidaatit:
            return (
                "lukituskonflikti",
                f"Lukittu kuski (paiva_kuski_id={teht.lukittu_kuski_id}) ei ole tarjolla tänään",
            )
    else:
        kandidaatit = list(kuskit)

    if not kandidaatit:
        return "ei_kuskia", "Yhtään kuskia ei ole tarjolla tänä ajankohtana"

    joku_ehtii_yksinaan = False
    for k in kandidaatit:
        tulos = ratkaise([teht], [k], ajoaika, parametrit)
        if tulos.ratkeaa and not tulos.sijoittamatta:
            joku_ehtii_yksinaan = True
            break

    if not joku_ehtii_yksinaan:
        if teht.henkiloita > 0 and not any(k.paikkoja >= teht.henkiloita for k in kandidaatit):
            suurin = max(k.paikkoja for k in kandidaatit)
            return "kapasiteetti", (
                f"Henkilömäärä ({teht.henkiloita}) ei mahdu mihinkään tarjolla olevaan "
                f"autoon (suurin kapasiteetti tarjolla: {suurin})"
            )
        return "aikaikkuna", (
            f"Yksikään tarjolla oleva kuski ei ehtisi tehtävään '{teht.nimi}' sen "
            "aikaikkunan puitteissa edes ilman muita tehtäviä"
        )

    return "aikaikkuna", (
        f"Tehtävä '{teht.nimi}' olisi teoriassa mahdollinen jollekin kuskille yksinään, "
        "mutta päivän muut tehtävät veivät kapasiteetin/ajan — kokeile lisätä kuskeja "
        "tai pidentää aikarajaa"
    )


def analysoi_sijoittamattomat(
    sijoittamatta_id: list[int],
    tehtavat: list[TehtavaRow],
    kuskit: list[KuskiRow],
    ajoaika: AjoaikaMatriisi,
    parametrit: OptimointiParametrit,
) -> list[dict]:
    tehtava_by_id = {t.id: t for t in tehtavat}
    tulokset = []
    for tid in sijoittamatta_id:
        teht = tehtava_by_id[tid]
        syy, selite = _selvita_syy(teht, kuskit, ajoaika, parametrit)
        tulokset.append({"tehtava_id": tid, "nimi": teht.nimi, "syy": syy, "selite": selite})
    return tulokset


_SOPIMUS_JARJESTYS = {
    SopimusTyyppi.KUUKAUSI: 0,
    SopimusTyyppi.PAIVA: 1,
    SopimusTyyppi.TUNTI: 2,
}


def vertaile_skenaarioita(
    tehtavat: list[TehtavaRow],
    kuskit: list[KuskiRow],
    ajoaika: AjoaikaMatriisi,
    parametrit: OptimointiParametrit,
    aikaraja_s: int = 10,
) -> list[dict]:
    """Montako kuskia kannattaa ottaa? Kuskit järjestetään sopimus-ensin
    (kuukausi -> paiva -> tunti, jo-maksetut/halvimmat ensin) ja kokeillaan
    kasvavia osajoukkoja."""
    sopimus_ensin = sorted(
        kuskit, key=lambda k: (_SOPIMUS_JARJESTYS[k.sopimus], k.paiva_kuski_id)
    )
    parametrit_lyhyt = replace(parametrit, aikaraja_s=aikaraja_s)

    skenaariot = []
    for n in range(1, len(sopimus_ensin) + 1):
        osajoukko = sopimus_ensin[:n]
        tulos = ratkaise(tehtavat, osajoukko, ajoaika, parametrit_lyhyt)
        ratkeaa = tulos.ratkeaa and not tulos.sijoittamatta
        kustannus_eur = None
        kuskeja_kaytossa = 0
        if ratkeaa:
            yhteenveto = koosta_kuskien_yhteenveto(tulos.keikat, osajoukko)
            kustannus_eur = round(sum(y.lisakustannus_eur for y in yhteenveto), 2)
            kuskeja_kaytossa = len(yhteenveto)
        skenaariot.append(
            {
                "kuskeja_tarjolla": n,
                "kuskeja_kaytossa": kuskeja_kaytossa,
                "kustannus_eur": kustannus_eur,
                "ratkeaa": ratkeaa,
                "halvin": False,
            }
        )

    kelvolliset = [s for s in skenaariot if s["ratkeaa"]]
    if kelvolliset:
        halvin = min(kelvolliset, key=lambda s: s["kustannus_eur"])
        halvin["halvin"] = True
    return skenaariot
