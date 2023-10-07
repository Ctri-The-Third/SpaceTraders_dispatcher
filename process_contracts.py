from conductorWK13 import Conductor, log_task
from dispatcherWK12 import BHVR_BUY_AND_DELIVER_OR_SELL
from straders_sdk.utils import waypoint_slicer
from datetime import datetime, timedelta
import json


class contracts(Conductor):
    def run(self):
        cargo_per_ship = 360
        requirements = ["HEAVY_FREIGHTER"]
        st = self.st
        unfulfilled_contracts = [
            c for c in st.view_my_contracts() if not c.fulfilled and c.accepted
        ]
        priority = 4

        for contract in unfulfilled_contracts:
            for deliverable in contract.deliverables:
                remaining = deliverable.units_required - deliverable.units_fulfilled
                params = {
                    "tradegood": deliverable.symbol,
                    "quantity": remaining,
                    "fulfil_wp": deliverable.destination_symbol,
                }
                if remaining > 0:
                    log_task(
                        self.connection,
                        BHVR_BUY_AND_DELIVER_OR_SELL,
                        requirements,
                        waypoint_slicer(deliverable.destination_symbol),
                        priority,
                        self.current_agent_symbol,
                        params,
                        datetime.utcnow() + timedelta(hours=2),
                    )
                priority += 0.01


if __name__ == "__main__":
    user = json.load(open("user.json"))
    contracts(user).run()
