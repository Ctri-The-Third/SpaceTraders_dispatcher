# version 2.1

This has broken a significant portion of the SDK. The main breaking points are changed models.
I'm going to use the Dispatcher and Conducter from week 16 to get behaviours up and running, and each crash will be met with a pair of integration tests for the API and Database respectively.

This will help in rapidly identifying and correcting future changes to the SDK.

I've decided that I'm going to match the SDK models to the new changes, even if that breaks backward compatibility. The number of calls necessary to properly replicate the 2.0 models would incur technical debt, and I'd rather just take the hit now.

I've noticed that everything breaking has triggered the "setback effect", which was identifed as the primary risk to this project losing momentum and wandiner off. Therefore the response to this patch, which is happening in the middle of tumultuous life events, is going to be key to whether or not we continue playing SpaceTraders or not.


## Step One - Build the jump gate
-  ✅ Our first step is to get the Dispatcher and Conductor working without crashing.
- Secondly we'll want a very rudimentary drone based solution to get credits flowing in.
  - we should target the nearest asteroid, not the first one returned by the DB.
  - fairly sure my first extractor is drifting to the target asteroid - need set in some behaviour for flight-mode handling for drones.
  - I've decided our fleet goal will be 10 extractors, 2 surveyors, 1 transporter. will need to do analytics on the effectiveness of this.
  - I'm going to skip upgrading behaviour for now and turn that off. Specifically all the values have changed and I want to make it less hard coded and more compatible with an aribtrary ship configuration coming in.
- Our "ships we might buy" assumes multiple shipyards automatically. In the early game, only one probe is needed, buying 2 extra has negatively impacted things.


Points 
- 🏆 cargo cuttoff in behaviour 8 is already pegged to the mining strength and cargo size of the ship. 👏