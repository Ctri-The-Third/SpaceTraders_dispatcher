py setup.py bdist_wheel
py -m pip uninstall spacetraders -y
py -m pip install dist/spacetraders-0.0.2-py3-none-any.whl
