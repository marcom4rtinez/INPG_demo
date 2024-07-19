from nornir.core.inventory import Host
from nornir.core.plugins.inventory import TransformFunctionRegister
from nornir_utils.plugins.inventory.transform_functions import load_credentials

def transform_function_host_cleanup(host: Host) -> None:
    """
    Override host data

    Args:

    """
    host.data = dict()
    load_credentials(host)

TransformFunctionRegister.register("transform_function_host_cleanup", transform_function_host_cleanup)