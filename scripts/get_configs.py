import requests, os
from infrahub_sdk import InfrahubClient
import asyncio



async def getContainerlabTopology():
    directory_path = "./generated-configs/clab"
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    client = InfrahubClient()
    topologies = await client.all(kind="TopologyTopology")

    for topology in topologies:
        await topology.artifacts.fetch()
        for artifact in topology.artifacts.peers:
            if (artifact.display_label == "Containerlab Topology"):
                artifact = downloadArtifact(artifact.peer.storage_id.value)
                with open(f'{directory_path}/{topology.name.value}.yml', 'w') as file:
                    file.write(artifact.decode('utf-8'))

async def getDeviceConfigs():
    directory_path = "./generated-configs/clab/configs/startup"
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    client = InfrahubClient()
    devices = await client.all(kind="InfraDevice")

    for device in devices:
        await device.artifacts.fetch()
        for artifact in device.artifacts.peers:
            if (str(artifact.display_label).startswith("Startup Config")):
                artifact = downloadArtifact(artifact.peer.storage_id.value)
                with open(f'{directory_path}/{device.name.value}.cfg', 'w') as file:
                    file.write(artifact.decode('utf-8'))

def downloadArtifact(artifact_id):
    response = requests.get(f"http://localhost:8000/api/storage/object/{artifact_id}")

    if response.status_code == 200:
        return(response.content)
    else:
        print(f"Failed to download file. Status code: {response.status_code}")



asyncio.run(getContainerlabTopology())
asyncio.run(getDeviceConfigs())