import fire
from spacetraders_v2.client_mediator import SpaceTraders

if __name__ == "__main__":
    st = SpaceTraders()
    fire.Fire(st)

    # there's potential here but we need to arrange things a bit better.
    # for the time being, stick to the plan.
