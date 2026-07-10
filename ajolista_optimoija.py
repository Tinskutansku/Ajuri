"""
AJOLISTA-OPTIMOIJA — prototyyppi (OR-Tools, pickup & delivery + aikaikkunat)
============================================================================
Ratkoo kuvauspäivän kuljetustehtävät kuskeille niin, että:
  - jokainen on perillä ennen call timea (max 30 min etuajassa)
  - autojen paikkamäärä riittää
  - kuskien tunnit ja Teme-tyylinen porrastettu palkka otetaan huomioon:
      * minimi 4 h maksetaan aina jos kuski käytössä
      * 0–8 h  = normaali tuntihinta
      * 8–10 h = +50 %
      * 10 h+  = tuplahinta
  - optimoija saa itse päättää montako kuskia kannattaa käyttää

Työaika alkaa ensimmäisestä noudosta ja päättyy viimeiseen jättöön
(kotimatkoja ei lasketa). Ajoajat ovat tässä prototyypissä synteettisiä
(koordinaattiruudukko); tuotantoversiossa matriisi haetaan esim.
OSRM:stä tai Google Distance Matrix -API:sta.

Testidata on KEKSITTYÄ, mutta rakenne jäljittelee oikeaa ajolistaa:
aamunoudot hotelleilta/kotoa, päivänsisäinen siirtymä LOC1 -> LOC2,
lounashaku, korttien vienti, lentokenttänouto ja paluukyydit wrapin
jälkeen.
"""

from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 1. PARAMETRIT
# ---------------------------------------------------------------------------

TUNTIHINTA = 22.0        # €/h
MINIMITUNNIT = 4         # h, maksetaan aina jos kuski käytössä
YLITYORAJA_1 = 8 * 60    # min, tämän jälkeen +50 %
YLITYORAJA_2 = 10 * 60   # min, tämän jälkeen tuplapalkka
MAX_VUORO = 13 * 60      # kova katto vuoron pituudelle
MAX_ETUAJASSA = 30       # min, aikaisintaan näin paljon ennen call timea

def hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"

def t(s: str) -> int:
    """'8:45' -> minuutteja keskiyöstä. Yön yli menevät ajat: '25:10'."""
    h, m = s.split(":")
    return int(h) * 60 + int(m)

# ---------------------------------------------------------------------------
# 2. PAIKAT (keksityt) — koordinaatit km-ruudukolla, ajoaika lasketaan niistä
# ---------------------------------------------------------------------------

PAIKAT = {
    "LOC1":        (10.0, 10.0),   # kuvauspaikka, "Tehtaankuja 2"
    "LOC2":        (16.0, 12.0),   # iltapäivän lokaatio
    "Hotelli A":   (4.0, 8.0),     # näyttelijähotelli keskustassa
    "Hotelli B":   (5.5, 6.5),
    "Koti Näytt3": (14.0, 4.0),    # kotimainen näyttelijä, oma osoite
    "Koti Näytt4": (2.0, 14.0),
    "Catering":    (12.0, 15.0),   # lounaan noutopiste
    "Toimisto":    (7.0, 9.0),     # kortit & printit
    "Lentokenttä": (22.0, 20.0),
    # kuskien kotiosoitteet
    "Koti Kuski1": (9.0, 9.0),
    "Koti Kuski2": (5.0, 7.0),
    "Koti Kuski3": (15.0, 11.0),
    "Koti Kuski4": (3.0, 12.0),
    "Koti Kuski5": (11.0, 14.0),
}

def ajoaika(a: str, b: str) -> int:
    """Synteettinen ajoaika minuutteina (linnuntie * mutkakerroin, 30 km/h)."""
    if a == b:
        return 0
    (x1, y1), (x2, y2) = PAIKAT[a], PAIKAT[b]
    km = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5 * 1.3
    return max(5, round(km / 30 * 60))

# ---------------------------------------------------------------------------
# 3. KUSKIT
# ---------------------------------------------------------------------------

@dataclass
class Kuski:
    nimi: str
    koti: str
    paikkoja: int          # matkustajapaikat autossa

KUSKIT = [
    Kuski("Kuski 1 (farmari)",   "Koti Kuski1", 4),
    Kuski("Kuski 2 (farmari)",   "Koti Kuski2", 4),
    Kuski("Kuski 3 (minibussi)", "Koti Kuski3", 8),
    Kuski("Kuski 4 (farmari)",   "Koti Kuski4", 4),
    Kuski("Kuski 5 (farmari)",   "Koti Kuski5", 4),
]

# ---------------------------------------------------------------------------
# 4. KULJETUSTEHTÄVÄT
#    Jokainen tehtävä = nouto -> jättö, henkilömäärä, aikaikkunat.
#    'perilla' = deadline (call time tms). 'nouto_aikaisintaan' rajaa
#    esim. wrapin jälkeiset paluut ja "15:00 jälkeen" -tyyppiset keikat.
# ---------------------------------------------------------------------------

@dataclass
class Tehtava:
    nimi: str
    mista: str
    mihin: str
    hloita: int = 1
    perilla_viim: int = None       # deadline perillä (min)
    perilla_aik: int = None        # aikaisintaan perillä (oletus: deadline-30)
    nouto_aik: int = None          # nouto aikaisintaan
    nouto_viim: int = None         # nouto viimeistään (esim. wrap-paluut: ei odotuttamista)
    huom: str = ""

CALL = t("8:45")
LOUNAS = t("12:30")
SIIRTYMA = t("14:00")     # LOC1 -> LOC2
WRAP = t("17:30")

TEHTAVAT = [
    # --- Aamunoudot (call timet porrastettu maskin mukaan) ---
    Tehtava("Näyttelijä 1 (pääosa)", "Hotelli A", "LOC1", 1, perilla_viim=t("6:30"), huom="maski 1,5 h"),
    Tehtava("Näyttelijä 2",          "Hotelli A", "LOC1", 1, perilla_viim=t("8:00")),
    Tehtava("Näyttelijä 3",          "Koti Näytt3", "LOC1", 1, perilla_viim=t("8:30")),
    Tehtava("Ohjaaja + apulaisohj.", "Hotelli B", "LOC1", 2, perilla_viim=CALL),
    Tehtava("Työryhmä-shuttle (4 hlö)", "Hotelli B", "LOC1", 4, perilla_viim=CALL),
    # --- Päivän sisällä ---
    Tehtava("Lounashaku", "Catering", "LOC1", 0, perilla_viim=LOUNAS - 25, nouto_aik=t("11:15"), huom="ruoka settiin ennen lounasta"),
    Tehtava("Näyttelijä 4 (iltapäiväkohtaus)", "Koti Näytt4", "LOC2", 1, perilla_viim=t("14:45")),
    # Siirtymä LOC1 -> LOC2 klo 14:00: näyttelijät ja osa ryhmästä kyyditään
    Tehtava("Siirtymä: näyttelijät 1-3", "LOC1", "LOC2", 3, nouto_aik=SIIRTYMA, perilla_viim=SIIRTYMA + 45),
    Tehtava("Siirtymä: ohjausosasto",    "LOC1", "LOC2", 3, nouto_aik=SIIRTYMA, perilla_viim=SIIRTYMA + 45),
    Tehtava("Kortit + printit toimistolta", "Toimisto", "LOC2", 0, nouto_aik=t("15:00"), perilla_viim=t("16:30")),
    Tehtava("Vieraileva näyttelijä lentokentältä", "Lentokenttä", "LOC2", 1,
            nouto_aik=t("15:40"), perilla_viim=t("16:45"), huom="lento laskeutuu 15:25"),
    # --- Paluut wrapin jälkeen: nouto max 25 min sisällä wrapista,
    #     ketään ei jätetä odottelemaan settiin ---
    Tehtava("Paluu: Näyttelijä 1", "LOC2", "Hotelli A", 1, nouto_aik=WRAP, nouto_viim=WRAP + 25),
    Tehtava("Paluu: Näyttelijä 2 + 4", "LOC2", "Hotelli A", 2, nouto_aik=WRAP, nouto_viim=WRAP + 25),
    Tehtava("Paluu: Näyttelijä 3", "LOC2", "Koti Näytt3", 1, nouto_aik=WRAP, nouto_viim=WRAP + 25),
    Tehtava("Paluu: ohjausosasto", "LOC2", "Hotelli B", 3, nouto_aik=WRAP, nouto_viim=WRAP + 25),
    Tehtava("Paluu: vieraileva näyttelijä", "LOC2", "Lentokenttä", 1,
            nouto_aik=t("18:00"), nouto_viim=t("18:50"), huom="lento 20:10"),
    Tehtava("Kortit labraan", "LOC2", "Toimisto", 0, nouto_aik=WRAP),
]

# ---------------------------------------------------------------------------
# 5. MALLIN RAKENNUS
# ---------------------------------------------------------------------------

def rakenna_ja_ratkaise(kuskit, aikaraja_s=15):
    """Palauttaa (reitit, pudotetut) tai None jos ei ratkaisua.
    reitit = lista per kuski: [(saapumisaika, node-tyyppi, tehtävä, paikka), ...]
    """
    # Solmut: 0..T-1 noudot, T..2T-1 jätöt, sitten kuskien start/end-dummyt
    T = len(TEHTAVAT)
    n_kuskia = len(kuskit)
    n_nodes = 2 * T + 2 * n_kuskia

    def node_paikka(node):
        if node < T:
            return TEHTAVAT[node].mista
        if node < 2 * T:
            return TEHTAVAT[node - T].mihin
        k = (node - 2 * T) // 2
        return kuskit[k].koti  # start ja end molemmat "koti"

    def on_end(node):
        return node >= 2 * T and (node - 2 * T) % 2 == 1

    starts = [2 * T + 2 * k for k in range(n_kuskia)]
    ends = [2 * T + 2 * k + 1 for k in range(n_kuskia)]

    manager = pywrapcp.RoutingIndexManager(n_nodes, n_kuskia, starts, ends)
    routing = pywrapcp.RoutingModel(manager)

    # --- Ajoaika / kaarikustannus ---
    def transit_cb(from_i, to_i):
        f, to = manager.IndexToNode(from_i), manager.IndexToNode(to_i)
        if on_end(to):
            return 0  # kotimatka ei ole työaikaa eikä kustannusta (yksinkertaistus)
        return ajoaika(node_paikka(f), node_paikka(to))

    transit_idx = routing.RegisterTransitCallback(transit_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    # --- Aikadimensio ---
    routing.AddDimension(transit_idx, 24 * 60, 30 * 60, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")

    for i, teht in enumerate(TEHTAVAT):
        pick = manager.NodeToIndex(i)
        drop = manager.NodeToIndex(i + T)
        # noutoikkuna
        alku = teht.nouto_aik if teht.nouto_aik is not None else 5 * 60
        loppu = teht.nouto_viim if teht.nouto_viim is not None else 26 * 60
        time_dim.CumulVar(pick).SetRange(alku, loppu)
        # jättöikkuna: perillä [deadline - MAX_ETUAJASSA, deadline]
        if teht.perilla_viim is not None:
            aik = teht.perilla_aik if teht.perilla_aik is not None else teht.perilla_viim - MAX_ETUAJASSA
            time_dim.CumulVar(drop).SetRange(aik, teht.perilla_viim)

    # --- Nouto & jättö samalla autolla, oikeassa järjestyksessä ---
    solver = routing.solver()
    for i in range(T):
        pick = manager.NodeToIndex(i)
        drop = manager.NodeToIndex(i + T)
        routing.AddPickupAndDelivery(pick, drop)
        solver.Add(routing.VehicleVar(pick) == routing.VehicleVar(drop))
        solver.Add(time_dim.CumulVar(pick) <= time_dim.CumulVar(drop))
        # Henkilö ei saa istua autossa kohtuuttomasti: kyytiaika enintään
        # suora ajoaika + 25 min (kimppakyytien kiertelyvara).
        if TEHTAVAT[i].hloita > 0:
            suora = ajoaika(TEHTAVAT[i].mista, TEHTAVAT[i].mihin)
            solver.Add(time_dim.CumulVar(drop) - time_dim.CumulVar(pick) <= suora + 25)
        # tehtävän saa pudottaa vain kovalla sakolla (raportoidaan jos putoaa)
        routing.AddDisjunction([pick], 1_000_000)
        routing.AddDisjunction([drop], 1_000_000)

    # --- Kapasiteetti ---
    def demand_cb(from_i):
        node = manager.IndexToNode(from_i)
        if node < T:
            return TEHTAVAT[node].hloita
        if node < 2 * T:
            return -TEHTAVAT[node - T].hloita
        return 0

    demand_idx = routing.RegisterUnaryTransitCallback(demand_cb)
    routing.AddDimensionWithVehicleCapacity(
        demand_idx, 0, [k.paikkoja for k in kuskit], True, "Seats")

    # --- Kustannusmalli ---
    # Kaikki kustannukset senteissä, jotta pysytään kokonaisluvuissa.
    # Palkka mallinnetaan vuoron pituuden (span) kautta:
    #   kiinteä kustannus = 4 h minimi, span 0-8 h ~ normaalihinta,
    #   soft span bound 8 h (lisäkerroin +50 %) ja 10 h (lisäkerroin +50 % lisää).
    c_min = int(TUNTIHINTA / 60 * 100)          # snt/min normaalihinta
    for v in range(n_kuskia):
        routing.SetFixedCostOfVehicle(int(MINIMITUNNIT * TUNTIHINTA * 100), v)
        time_dim.SetSpanCostCoefficientForVehicle(c_min, v)
        time_dim.SetSpanUpperBoundForVehicle(MAX_VUORO, v)
        time_dim.SetSoftSpanUpperBoundForVehicle(
            pywrapcp.BoundCost(YLITYORAJA_1, c_min // 2), v)
        # 10 h+ tuplaportaan approksimaatio kvadraattisella sakolla,
        # jotta ratkaisija oikeasti karttaa ylipitkiä vuoroja. Tarkka
        # palkka lasketaan aina jälkikäteen raporttiin.
        time_dim.SetQuadraticCostSoftSpanUpperBoundForVehicle(
            pywrapcp.BoundCost(YLITYORAJA_2, 2), v)
        # Vuoro saa alkaa myöhään -> kotona odottelu ei kerrytä spania:
        routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(routing.End(v)))
        routing.AddVariableMaximizedByFinalizer(time_dim.CumulVar(routing.Start(v)))

    # --- Haku ---
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromSeconds(aikaraja_s)

    sol = routing.SolveWithParameters(params)
    if sol is None:
        return None

    # --- Ratkaisun purku ---
    reitit = []
    pudotetut = []
    for i in range(T):
        if sol.Value(routing.NextVar(manager.NodeToIndex(i))) == manager.NodeToIndex(i):
            pass  # ei luotettava tapa; hoidetaan ActiveVar-tarkistuksella alla
    for i in range(T):
        idx = manager.NodeToIndex(i)
        if not sol.Value(routing.ActiveVar(idx)):
            pudotetut.append(TEHTAVAT[i].nimi)

    for v in range(n_kuskia):
        rivi = []
        idx = routing.Start(v)
        while not routing.IsEnd(idx):
            node = manager.IndexToNode(idx)
            aika = sol.Value(time_dim.CumulVar(idx))
            if node < T:
                rivi.append((aika, "NOUTO", TEHTAVAT[node], node_paikka(node)))
            elif node < 2 * T:
                rivi.append((aika, "JÄTTÖ", TEHTAVAT[node - T], node_paikka(node)))
            idx = sol.Value(routing.NextVar(idx))
        reitit.append(rivi)
    return reitit, pudotetut


# ---------------------------------------------------------------------------
# 6. PALKKALASKENTA (tarkka, porrastettu) + RAPORTTI
# ---------------------------------------------------------------------------

def palkka(min_tyoaika: int) -> float:
    """Työminuutit -> € porrastetulla taksalla, 4 h minimi."""
    h = max(min_tyoaika / 60, MINIMITUNNIT)
    perus = min(h, 8) * TUNTIHINTA
    ot1 = max(0, min(h, 10) - 8) * TUNTIHINTA * 1.5
    ot2 = max(0, h - 10) * TUNTIHINTA * 2.0
    return perus + ot1 + ot2

def raportti(reitit, pudotetut, kuskit):
    yht = 0.0
    print("=" * 78)
    print(f"{'AJOLISTA — OPTIMOITU':^78}")
    print(f"{'Call ' + hhmm(CALL) + '  |  Lounas ' + hhmm(LOUNAS) + '  |  Siirtymä LOC1->LOC2 ' + hhmm(SIIRTYMA) + '  |  Wrap ' + hhmm(WRAP):^78}")
    print("=" * 78)
    for v, rivi in enumerate(reitit):
        if not rivi:
            continue
        alku = rivi[0][0]                      # työaika alkaa ekasta noudosta
        loppu = max(a for a, *_ in rivi)       # viimeinen jättö
        kesto = loppu - alku
        e = palkka(kesto)
        yht += e
        print(f"\n▐ {kuskit[v].nimi}  |  vuoro {hhmm(alku)}–{hhmm(loppu)} "
              f"({kesto // 60}h {kesto % 60:02d}min)  |  {e:.0f} €")
        print("-" * 78)
        for aika, tyyppi, teht, paikka in rivi:
            huom = f"  [{teht.huom}]" if teht.huom and tyyppi == "NOUTO" else ""
            print(f"  {hhmm(aika)}  {tyyppi:<6} {teht.nimi:<38} @ {paikka}{huom}")
    print("\n" + "=" * 78)
    kaytossa = sum(1 for r in reitit if r)
    print(f"Kuskeja käytössä: {kaytossa}/{len(kuskit)}   |   PÄIVÄN KULJETUSKUSTANNUS: {yht:.0f} €")
    if pudotetut:
        print(f"⚠ SIJOITTAMATTA JÄI: {', '.join(pudotetut)}")
    else:
        print("Kaikki tehtävät sijoitettu. ✔")
    return yht


if __name__ == "__main__":
    print("Ratkaistaan koko kalustolla (optimoija valitsee kuskimäärän)...\n")
    tulos = rakenna_ja_ratkaise(KUSKIT, aikaraja_s=30)
    if tulos is None:
        print("Ei ratkaisua!")
        raise SystemExit(1)
    reitit, pudotetut = tulos
    raportti(reitit, pudotetut, KUSKIT)

    # Skenaariovertailu: pakotettu kuskimäärä
    print("\n\nSKENAARIOVERTAILU — montako kuskia kannattaa ottaa?")
    print("-" * 60)
    for n in (3, 4, 5):
        osa = KUSKIT[:n]
        tulos = rakenna_ja_ratkaise(osa, aikaraja_s=15)
        if tulos is None:
            print(f"  {n} kuskia: EI RATKAISUA (aikaikkunat eivät riitä)")
            continue
        reitit, pudotetut = tulos
        if pudotetut:
            print(f"  {n} kuskia: {len(pudotetut)} tehtävää jäi sijoittamatta -> ei kelpaa")
            continue
        kust = sum(palkka(max(a for a, *_ in r) - r[0][0]) for r in reitit if r)
        tunnit = [f"{(max(a for a,*_ in r) - r[0][0]) / 60:.1f}h" for r in reitit if r]
        print(f"  {n} kuskia: {kust:6.0f} €   (vuorot: {', '.join(tunnit)})")
