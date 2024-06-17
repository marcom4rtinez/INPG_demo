import os, argparse, subprocess
from infrahub_sdk import InfrahubClientSync



def get_containerlab_topology():
    directory_path = "./generated-configs/clab"
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    client = InfrahubClientSync.init()
    topologies = client.all(kind="TopologyTopology")

    for topology in topologies:
        artifact = topology.artifact_fetch("Containerlab Topology")
        with open(f'{directory_path}/{topology.name.value}.yml', 'w') as file:
            file.write(artifact)

def get_device_configs():
    directory_path = "./generated-configs/clab/configs/startup"
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    client = InfrahubClientSync.init()
    devices = client.all(kind="InfraDevice")

    for device in devices:
        device.artifacts.fetch()
        for artifact in device.artifacts.peers:
            if (str(artifact.display_label).startswith("Startup Config")):
                artifact = device.artifact_fetch(artifact.display_label)
                with open(f'{directory_path}/{device.name.value}.cfg', 'w') as file:
                    file.write(artifact)


def get_nuts_tests():
    directory_path = "./nuts/tests"
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    client = InfrahubClientSync.init()
    devices = client.all(kind="InfraDevice")

    for device in devices:
        device.artifacts.fetch()
        for artifact in device.artifacts.peers:
            if (str(artifact.display_label).startswith("NUTS tests")):
                artifact = device.artifact_fetch(artifact.display_label)
                with open(f'{directory_path}/test_{device.name.value}.yaml', 'w') as file:
                    file.write(artifact)

def execute(command):
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True)
        print("Waiting... This might take a while")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(e.stderr)

def deploy_containerlab_topology():
    command = ["sudo", "-E", "containerlab", "deploy", "-t", "./generated-configs/clab/fra05-pod1.yml", "--reconfigure"]
    execute(command)


def destroy_containerlab_topology():
    command = ["sudo", "-E", "containerlab", "destroy", "-t", "./generated-configs/clab/fra05-pod1.yml"]
    execute(command)
    print("Containerlab deleted")


def main():
    parser = argparse.ArgumentParser(description='Helper tool to allow fetching artifacts')
    parser.add_argument('--nuts-tests', '-n', action='store_true', help='Trigger get_nuts_tests')
    parser.add_argument('--containerlab-topology', '-c', action='store_true', help='Trigger get_containerlab_topology')
    parser.add_argument('--device-configs', '-d', action='store_true', help='Trigger get_device_configs')
    parser.add_argument('--deploy-containerlab', '--deploy', action='store_true', help='Trigger deploy_containerlab_topology')
    parser.add_argument('--destroy-containerlab', '--destroy', action='store_true', help='Trigger deploy_containerlab_topology')
    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        return 0

    actions = [
        (args.nuts_tests, get_nuts_tests),
        (args.containerlab_topology, get_containerlab_topology),
        (args.device_configs, get_device_configs),
        (args.deploy_containerlab, deploy_containerlab_topology),
        (args.destroy_containerlab, destroy_containerlab_topology),
    ]

    for flag, func in actions:
        if flag:
            func()



if __name__ == "__main__":
    main()