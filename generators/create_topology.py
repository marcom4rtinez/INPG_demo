import logging

from typing import  List

from infrahub_sdk import InfrahubClient, NodeStore

from utils import create_and_add_to_batch, populate_local_store

# flake8: noqa
# pylint: skip-file

NETWORK_STRATEGY = (
    # Underlay, Overlay, Stategy Type (name and description will be auto-generated)
    ("ebgp-ebgp", "ebgp", "ebgp", "evpn"),
    ("ospf-ebgp", "ospf", "ebgp", "evpn"),
    ("isis-ebgp", "isis", "ebgp", "evpn"),
    ("ospf-ibgp", "ospf", "ibgp", "evpn"),
    ("isis-ibgp", "isis", "ibgp", "evpn"),
)

TOPOLOGY = (
    # name, description, Location shortname, strategy
    ("fra05-pod1", "Small Fabric in Equinix FRA05", "FRA05", "ebgp-ebgp"),
    # ("ams9-pod1", "Big Fabric in Interxion AMS9", "AMS9", None),
    ("de1-pod1", "Medium Fabric in Equinix DE1", "DE1", "ebgp-ebgp"),
    ("de2-pod1", "Medium Fabric in Equinix DE2", "DE2", "ospf-ibgp"),
    ("denver-mpls1", "Medium MPLS in Denver Metro (DE1+DE2)", "DEN", "isis-ibgp"),
)

TOPOLOGY_ELEMENTS = {
    # Topology [ Quantity, Device Role, Device Type, mtu, mlag support, is border]
    "fra05-pod1": [
        ( 2, "spine", "CCS-720DP-48S-2F", 1500, False, False),
        ( 2, "leaf", "CCS-720DP-48S-2F", 1500, True, False),
    ],
    # "ams9-pod1": [
    #     ( 4, "spine", "CCS-720DP-48S-2F", 9192, False, False),
    #     ( 8, "leaf", "NCS-5501-SE", 9192, True, False),
    #     ( 2, "leaf", "CCS-720DP-48S-2F", 9192, True, True), # borderleaf
    # ],
    "de1-pod1": [
        ( 2, "spine", "CCS-720DP-48S-2F", 9192, False, True), # spine as border
        ( 4, "leaf", "NCS-5501-SE", 9192, True, False),
    ],
    "de2-pod1": [
        ( 2, "spine", "CCS-720DP-48S-2F", 9192, False, False),
        ( 4, "leaf", "NCS-5501-SE", 9192, True, False),
        ( 2, "leaf", "CCS-720DP-48S-2F", 9192, True, True), # borderleaf
    ],
    "denver-mpls1": [
        ( 2, "route_reflector", "DCS-7280DR3-24-F", 9192, False, False),
        ( 4, "pe_router", "DCS-7280DR3-24-F", 9192, True, False),
        ( 2, "p_router", "DCS-7280DR3-24-F", 9192, True, True), # PE as border
    ],
}


store = NodeStore()

async def create_topology_strategies(client: InfrahubClient, log: logging.Logger, branch: str):
    log.info("Creating Network Strategies")
    # Create Network Strategies
    account = store.get(key="pop-builder", kind="CoreAccount")
    batch = await client.create_batch()
    for strategy in NETWORK_STRATEGY:
        name = strategy[0]
        underlay =  strategy[1]
        overlay = strategy[2]
        strategy_type = strategy[3]
        description = f"Using {underlay.upper()} as underlay with {overlay.upper()} as overlay"
        data = {
            "name": {"value": name, "source": account.id},
            "description": {"value": description, "source": account.id},
            "underlay": {"value": underlay, "source": account.id},
            "overlay": {"value": overlay, "source": account.id},
        }
        await create_and_add_to_batch(
            client=client,
            log=log,
            branch=branch,
            object_name=name,
            kind_name=f"Topology{strategy_type.upper()}Strategy",
            data=data,
            store=store,
            batch=batch
            )
    async for node, _ in batch.execute():
        accessor = f"{node._schema.default_filter.split('__')[0]}"
        log.info(f"- Created {node._schema.kind} - {getattr(node, accessor).value}")

async def create_topology(client: InfrahubClient, log: logging.Logger, branch: str):
    # ------------------------------------------
    # Create Topology
    # ------------------------------------------
    log.info("Creating Topologies")
    # Create Topology Group
    batch = await client.create_batch()
    for topology in TOPOLOGY:
        group_name = f"{topology[0]}_topology"
        data={
           "name": group_name,
        }
        await create_and_add_to_batch(
            client=client,
            log=log,
            branch=branch,
            object_name=group_name,
            kind_name="CoreStandardGroup",
            data=data,
            store=store,
            batch=batch
            )
    async for node, _ in batch.execute():
        accessor = f"{node._schema.default_filter.split('__')[0]}"
        log.info(f"- Created {node._schema.kind} - {getattr(node, accessor).value}")

    # Create Topology
    account = store.get(key="pop-builder", kind="CoreAccount")
    batch = await client.create_batch()
    strategy_dict = {name: type for name, underlay, overlay, type in NETWORK_STRATEGY}
    for topology in TOPOLOGY:
        topology_strategy = topology[3]
        topology_location = topology[2]
        data = {
            "name": {"value": topology[0], "source": account.id},
            "description": {"value": topology[1], "source": account.id},
        }
        if topology_strategy:
            strategy_type = strategy_dict.get(topology[3], None).upper()
            data["strategy"] = store.get(kind=f"Topology{strategy_type}Strategy", key=topology_strategy).id
        if topology_location:
            topology_location_object = store.get(key=topology[2])
            if topology_location_object:
                data["location"] = {"id": topology_location_object.id}
        await create_and_add_to_batch(
            client=client,
            log=log,
            branch=branch,
            object_name=topology[0],
            kind_name="TopologyTopology",
            data=data,
            store=store,
            batch=batch
            )
    async for node, _ in batch.execute():
        accessor = f"{node._schema.default_filter.split('__')[0]}"
        log.info(f"- Created {node._schema.kind} - {getattr(node, accessor).value}")

    batch = await client.create_batch()
    for topology in TOPOLOGY:
        # Add Topology to Topology Group
        topology_name = topology[0]
        topology_group = await client.get(name__value=f"{topology_name}_topology", kind="CoreStandardGroup")
        topology_obj = await client.get(name__value=topology_name, kind="TopologyTopology")
        await topology_group.members.fetch()
        topology_group.members.add(topology_obj.id)
        await topology_group.save()
        log.info(f"- Add {topology_name} to {topology_group.name.value} CoreStandardGroup")

        topology_object = store.get(key=topology_name, kind="TopologyTopology")
        if topology[2]:
            topology_location_object = store.get(key=topology[2])
            if topology_location_object:
                topology_object.location = topology_location_object
                await topology_object.save()
            log.info(f"- Add {topology_name} to {topology_location_object.name.value} Location")

        # ------------------------------------------
        # Create Topology Elements
        # ------------------------------------------
        for element_idx, element in enumerate(TOPOLOGY_ELEMENTS[topology_name]):
            if not element:
                continue
            device_type_id = store.get(kind="InfraDeviceType", key=element[2]).id
            element_role = element[1]
            element_name = f"{element_role}-{topology_name.lower()}"
            element_description = f"{element_role.title()} for Topology {topology_name.title()}"
            if element[5] and element_role != "spine":
                element_name = f"border-{element_role}-{topology_name.lower()}"
                element_description = f"Border {element_role.title()} for Topology {topology_name.title()}"
            data = {
                "name":{"value": element_name, "is_protected": True, "owner": account.id},
                "description": {"value": element_description, "source": account.id},
                "quantity": {"value": element[0], "source": account.id},
                "device_role": {"value": element_role, "source": account.id, "is_protected": True, "owner": account.id},
                "device_type": device_type_id,
                "topology": topology_object.id,
                "mlag_support": element[4],
                "border": element[5],
                "mtu": element[3],
            }
            await create_and_add_to_batch(
                client=client,
                log=log,
                branch=branch,
                object_name=element_name,
                kind_name="TopologyPhysicalElement",
                data=data,
                store=store,
                batch=batch
                )

    # Add Topologies to Topology Summary Group
    all_topologies_group = await client.get(name__value=f"all_topologies", kind="CoreStandardGroup")
    await all_topologies_group.members.fetch()
    for topology in TOPOLOGY:
        topology_name = topology[0]
        topology_obj = await client.get(name__value=topology_name, kind="TopologyTopology")
        all_topologies_group.members.add(topology_obj.id)
        log.info(f"- Add {topology_name} to {topology_group.name.value} CoreStandardGroup")
    await all_topologies_group.save()

    async for node, _ in batch.execute():
        accessor = f"{node._schema.default_filter.split('__')[0]}"
        log.info(f"- Created {node._schema.kind} - {getattr(node, accessor).value}")

# ---------------------------------------------------------------
# Use the `infrahubctl run` command line to execute this script
#
#   infrahubctl run models/infrastructure_edge.py
#
# ---------------------------------------------------------------
async def run(client: InfrahubClient, log: logging.Logger, branch: str, **kwargs) -> None:
    log.info("Retrieving objects from Infrahub")
    try:
        accounts=await client.all("CoreAccount")
        populate_local_store(objects=accounts, key_type="name", store=store)
        tenants=await client.all("OrganizationTenant")
        populate_local_store(objects=tenants, key_type="name", store=store)
        providers=await client.all("OrganizationProvider")
        populate_local_store(objects=providers, key_type="name", store=store)
        manufacturers=await client.all("OrganizationManufacturer")
        populate_local_store(objects=manufacturers, key_type="name", store=store)
        autonomous_systems=await client.all("InfraAutonomousSystem")
        populate_local_store(objects=autonomous_systems, key_type="name", store=store)
        platforms=await client.all("InfraPlatform")
        populate_local_store(objects=platforms, key_type="name", store=store)
        device_types=await client.all("InfraDeviceType")
        populate_local_store(objects=device_types, key_type="name", store=store)
        locations=await client.all("LocationGeneric")
        populate_local_store(objects=locations, key_type="shortname", store=store)

    except Exception as e:
        log.error(f"Fail to populate due to {e}")
        exit(1)

    await create_topology_strategies(client=client, branch=branch, log=log)
    await create_topology(client=client, branch=branch, log=log)
