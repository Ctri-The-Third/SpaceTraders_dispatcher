from behaviours.extract_and_chill import (
    ExtractAndChill,
    BEHAVIOUR_NAME as BHVR_EXTRACT_AND_CHILL,
)
from behaviours.buy_and_sell_dripfeed import (
    BuyAndSellDripfeed,
    BEHAVIOUR_NAME as BHVR_BUY_AND_SELL_DRIPFEED,
)
from behaviours.extract_and_sell import (
    ExtractAndGoSell,
    BEHAVIOUR_NAME as BHVR_EXTRACT_AND_GO_SELL,
)
from behaviours.receive_and_fulfill import (
    ReceiveAndFulfillOrSell_3,
    BEHAVIOUR_NAME as BHVR_RECEIVE_AND_FULFILL,
)
from behaviours.generic_behaviour import Behaviour
from behaviours.extract_and_transfer import (
    ExtractAndTransfer_8,
    BEHAVIOUR_NAME as BHVR_EXTRACT_AND_TRANSFER,
)
from behaviours.explore_system import (
    ExploreSystem,
    BEHAVIOUR_NAME as BHVR_EXPLORE_SYSTEM,
)
from behaviours.monitor_cheapest_price import (
    MonitorCheapestShipyard,
    BEHAVIOUR_NAME as BHVR_MONITOR_CHEAPEST_PRICE,
)
from behaviours.buy_and_deliver_or_sell import (
    BuyAndDeliverOrSell_6,
    BEHAVIOUR_NAME as BHVR_BUY_AND_DELIVER_OR_SELL,
)

from behaviours.receive_and_refine import (
    ReceiveAndRefine,
    BEHAVIOUR_NAME as BHVR_RECEIVE_AND_REFINE,
)
from behaviours.extract_and_fulfill import (
    ExtractAndFulfill_7,
    BEHAVIOUR_NAME as BHVR_EXTRACT_AND_FULFILL,
)

from behaviours.upgrade_ship_to_specs import (
    FindMountsAndEquip,
    BEHAVIOUR_NAME as BHVR_UPGRADE_TO_SPEC,
)
from behaviours.chill_and_survey import (
    ChillAndSurvey,
    BEHAVIOUR_NAME as BHVR_CHILL_AND_SURVEY,
)
from behaviours.refuel_all_fuel_exchanges_in_system import (
    RefuelAnExchange,
    BEHAVIOUR_NAME as BHVR_REFUEL_ALL_IN_SYSTEM,
)
from behaviours.single_stable_trade import (
    SingleStableTrade,
    BEHAVIOUR_NAME as BHVR_SINGLE_STABLE_TRADE,
)
from behaviours.monitor_specific_location import (
    MonitorPrices,
    BEHAVIOUR_NAME as BHVR_MONITOR_SPECIFIC_LOCATION,
)
from behaviours.take_from_extractors_and_fulfill import (
    TakeFromExactorsAndFulfillOrSell_9,
    BEHAVIOUR_NAME as BHVR_TAKE_FROM_EXTRACTORS_AND_FULFILL,
)
from behaviours.siphon_and_chill import (
    SiphonAndChill,
    BEHAVIOUR_NAME as BHVR_SIPHON_AND_CHILL,
)
from behaviours.manage_specific_export import (
    ManageSpecifcExport,
    BEHAVIOUR_NAME as BHVR_MANAGE_SPECIFIC_EXPORT,
)
from behaviours.construct_a_jumpgate import (
    ConstructJumpgate,
    BEHAVIOUR_NAME as BHVR_CONSTRUCT_JUMP_GATE,
)
from behaviours.sell_or_jettison_all_cargo import (
    SellOrDitch,
    BEHAVIOUR_NAME as BHVR_SELL_OR_JETTISON_ALL_CARGO,
)
from behaviours.chain_trade import ChainTrade, BEHAVIOUR_NAME as BHVR_CHAIN_TRADE

from behaviours.manage_supply_chain import (
    ManageManufactureChain,
    BEHAVIOUR_NAME as BHVR_MANAGE_SUPPLY_CHAIN,
)

from behaviours.emergency_reboot import (
    EmergencyReboot,
    BEHAVIOUR_NAME as BHVR_EMERGENCY_REBOOT,
)

from behaviours.manage_contracts import (
    ExecuteContracts,
    BEHAVIOUR_NAME as BHVR_EXECUTE_CONTRACTS,
)

from behaviours.chain_trade_est import (
    ChainTradeEST,
    BEHAVIOUR_NAME as BHVR_CHAIN_TRADE_EST,
)

from behaviours.go_and_buy_a_ship import (
    GoAndBuyShip,
    BEHAVIOUR_NAME as BHVR_GO_AND_BUY_A_SHIP,
)

from behaviours.warp_to_system import (
    WarpToSystem,
    BEHAVIOUR_NAME as BHVR_WARP_TO_SYSTEM,
)

behaviours_and_classes = {
    BHVR_EXTRACT_AND_GO_SELL: ExtractAndGoSell,
    BHVR_RECEIVE_AND_FULFILL: ReceiveAndFulfillOrSell_3,
    BHVR_EXTRACT_AND_TRANSFER: ExtractAndTransfer_8,
    # BHVR_REMOTE_SCAN_AND_SURV: RemoteScanWaypoints,
    BHVR_EXPLORE_SYSTEM: ExploreSystem,
    BHVR_MONITOR_CHEAPEST_PRICE: MonitorCheapestShipyard,
    BHVR_BUY_AND_DELIVER_OR_SELL: BuyAndDeliverOrSell_6,
    # BHVR_EXTRACT_AND_FULFILL: ExtractAndFulfill_7,
    BHVR_RECEIVE_AND_REFINE: ReceiveAndRefine,
    BHVR_UPGRADE_TO_SPEC: FindMountsAndEquip,
    BHVR_CHILL_AND_SURVEY: ChillAndSurvey,
    BHVR_REFUEL_ALL_IN_SYSTEM: RefuelAnExchange,
    BHVR_SINGLE_STABLE_TRADE: SingleStableTrade,
    BHVR_BUY_AND_SELL_DRIPFEED: BuyAndSellDripfeed,
    BHVR_MONITOR_SPECIFIC_LOCATION: MonitorPrices,
    BHVR_EXTRACT_AND_CHILL: ExtractAndChill,
    BHVR_TAKE_FROM_EXTRACTORS_AND_FULFILL: TakeFromExactorsAndFulfillOrSell_9,
    BHVR_SIPHON_AND_CHILL: SiphonAndChill,
    BHVR_MANAGE_SPECIFIC_EXPORT: ManageSpecifcExport,
    BHVR_CONSTRUCT_JUMP_GATE: ConstructJumpgate,
    BHVR_SELL_OR_JETTISON_ALL_CARGO: SellOrDitch,
    BHVR_CHAIN_TRADE: ChainTrade,
    BHVR_MANAGE_SUPPLY_CHAIN: ManageManufactureChain,
    BHVR_EMERGENCY_REBOOT: EmergencyReboot,
    BHVR_EXECUTE_CONTRACTS: ExecuteContracts,
    BHVR_CHAIN_TRADE_EST: ChainTradeEST,
    BHVR_GO_AND_BUY_A_SHIP: GoAndBuyShip,
    BHVR_WARP_TO_SYSTEM: WarpToSystem,
}
