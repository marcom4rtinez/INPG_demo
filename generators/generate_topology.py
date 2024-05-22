import logging
import uuid
from collections import defaultdict
from ipaddress import IPv4Network
from typing import Any, Dict, List, Optional

from infrahub_sdk import InfrahubBatch, UUIDT, InfrahubClient, InfrahubNode, NodeStore

from create_location import LOCATION_SUPERNETS, LOCATION_MGMTS, EXTERNAL_NETWORKS
from utils import populate_local_store, create_and_save, create_and_add_to_batch


# flake8: noqa
# pylint: skip-file

INTERFACE_MGMT_NAME = {
    "QFX5110-48S-S": "fxp0",
    "CCS-720DP-48S-2F": "Management0",
    "NCS-5501-SE": "MgmtEth0/RP0/CPU0/0",
    "ASR1002-HX": "GigabitEthernet0",
    "linux": "Eth0"
}

INTERFACE_LOOP_NAME = {
    "QFX5110-48S-S": "lo0",
    "CCS-720DP-48S-2F": "Loopback0",
    "NCS-5501-SE": "Loopback0",
    "ASR1002-HX": "Loopback 0",
    "linux": "lo"
}

INTERFACE_VTEP_NAME = {
    "QFX5110-48S-S": "lo1",
    "CCS-720DP-48S-2F": "Loopback1",
    "NCS-5501-SE": "Loopback1",
    "ASR1002-HX": "Loopback 1",
    "linux": "lo1"
}

# TODO replace name by real name
DEVICES_INTERFACES = {
    # Device Type [ Interfaces ]
    "QFX5110-48S-S": [
        "xe-0/0/0",
        "xe-0/0/1",
        "xe-0/0/2",
        "xe-0/0/3",
        "xe-0/0/4",
        "xe-0/0/5",
        "xe-0/0/6",
        "xe-0/0/7",
        "xe-0/0/8",
        "xe-0/0/9",
        "xe-0/0/10",
        "xe-0/0/11",
        "xe-0/0/12",
        "xe-0/0/13",
    ],
    "CCS-720DP-48S-2F": [
        "Ethernet1",
        "Ethernet2",
        "Ethernet3",
        "Ethernet4",
        "Ethernet5",
        "Ethernet6",
        "Ethernet7",
        "Ethernet8",
        "Ethernet9",
        "Ethernet10",
        "Ethernet11",
        "Ethernet12",
        "Ethernet13",
        "Ethernet14",
    ],
    "NCS-5501-SE": [
        "Ethernet1",
        "Ethernet2",
        "Ethernet3",
        "Ethernet4",
        "Ethernet5",
        "Ethernet6",
        "Ethernet7",
        "Ethernet8",
        "Ethernet9",
        "Ethernet10",
        "Ethernet11",
        "Ethernet12",
        "Ethernet13",
        "Ethernet14",
    ],
    "ASR1002-HX": [
        "Ethernet1",
        "Ethernet2",
        "Ethernet3",
        "Ethernet4",
        "Ethernet5",
        "Ethernet6",
        "Ethernet7",
        "Ethernet8",
        "Ethernet9",
        "Ethernet10",
        "Ethernet11",
        "Ethernet12",
        "Ethernet13",
        "Ethernet14",
    ]
}

# 14 Interfaces to fit DEVICES_INTERFACES
INTERFACE_ROLES_MAPPING = {
    "spine": [
        "leaf",     # Ethernet1  - leaf1 (L3)
        "leaf",     # Ethernet2  - leaf2 (L3)
        "leaf",     # Ethernet3  - leaf3 (L3)
        "leaf",     # Ethernet4  - leaf4 (L3)
        "leaf",     # Ethernet5  - leaf5 (L3)
        "leaf",     # Ethernet6  - leaf6 (L3)
        "leaf",     # Ethernet7  - leaf7 (L3)
        "leaf",     # Ethernet8  - leaf8 (L3)
        "leaf",     # Ethernet9  - leaf9 (L3)
        "leaf",     # Ethernet10 - leaf10 (L3)
        "uplink",   # Ethernet11
        "uplink",   # Ethernet12
        "spare",    # Ethernet13
        "spare",    # Ethernet14
    ],
    "leaf": [
        "server",   # Ethernet1
        "server",   # Ethernet2
        "server",   # Ethernet3
        "server",   # Ethernet4
        "server",   # Ethernet5
        "server",   # Ethernet6
        "spare",    # Ethernet7
        "peer",     # Ethernet8  - leaf (L2)
        "peer",     # Ethernet9  - leaf (L2)
        "uplink",   # Ethernet10 - spine1 (L3)
        "uplink",   # Ethernet11 - spine2 (L3)
        "uplink",   # Ethernet12 - spine3 (L3)
        "uplink",   # Ethernet13 - spine4 (L3)
        "spare",    # Ethernet14
    ]
}

L3_ROLE_MAPPING = [
    "backbone",
    "upstream",
    "peering",
    "uplink",
    "leaf",
    "spare"
]
L2_ROLE_MAPPING = [
    "peer",
    "server",
]

DEVICE_INTERFACE_OBJS: Dict[str, List[InfrahubNode]] = defaultdict(list)

# Mapping Dropdown Role and Status here
ACTIVE_STATUS = "active"
PROVISIONING_STATUS = "provisioning"
LOOPBACK_ROLE = "loopback"
MGMT_ROLE = "management"

store = NodeStore()

def get_interface_names(device_type: str, device_role: str, interface_role: str) -> Optional[List]:
    if device_type not in DEVICES_INTERFACES:
        return None
    if device_role not in INTERFACE_ROLES_MAPPING:
        return None

    # Mapping of roles to interface indices
    role_indices = [i for i, r in enumerate(INTERFACE_ROLES_MAPPING[device_role]) if r == interface_role]

    # Get the interface names based on the indices for the specific device model
    interface_names = [DEVICES_INTERFACES[device_type][i] for i in role_indices]

    return interface_names

async def upsert_interface(
        client: InfrahubClient,
        log: logging.Logger,
        branch: str,
        device_name: str,
        intf_name: str,
        data: Dict[str, Any],
        store: NodeStore,
        batch: Optional[InfrahubBatch] = None,
        )-> InfrahubNode:

    kind_name = data['kind_name']
    data.pop('kind_name')
    found_iface = None
    for tmp_iface in DEVICE_INTERFACE_OBJS[device_name]:
        if tmp_iface.name.value == intf_name:
            found_iface = tmp_iface
            break
    if found_iface is not None:
        data["id"] = found_iface.id

    if batch:
        interface_obj = await create_and_add_to_batch(
            client=client,
            log=log,
            branch=branch,
            object_name=f"{device_name}-{intf_name}",
            kind_name=kind_name,
            data=data,
            store=store,
            batch=batch
        )
    else:
        interface_obj = await create_and_save(
            client=client,
            log=log,
            branch=branch,
            object_name=f"{device_name}-{intf_name}",
            kind_name=kind_name,
            data=data,
            store=store,
        )
    return interface_obj

async def upsert_ip_address(
        client: InfrahubClient,
        log: logging.Logger,
        branch: str,
        prefix_obj : InfrahubNode,
        device_name: str,
        interface_obj: InfrahubNode,
        description: str,
        account_pop_id: str,
        address: str,
        store: NodeStore,
        batch: Optional[InfrahubBatch] = None,
        ) -> None:
    if prefix_obj:
        prefix_id = prefix_obj.id
        namespace_id = prefix_obj.ip_namespace.id
    else:
        prefix_id = None
        namespace_id = None
    data = {
        "ip_namespace": {"id": namespace_id, "source": account_pop_id},
        "interface": {"id": interface_obj.id, "source": account_pop_id},
        "description": {"value": description},
        "address": {"value": address, "source": account_pop_id},
    }
    if batch:
        ip_obj = await create_and_add_to_batch(
            client=client,
            log=log,
            branch=branch,
            object_name=f"{device_name}-{interface_obj.name.value}-address",
            kind_name="InfraIPAddress",
            data=data,
            store=store,
            batch=batch,
        )
    else:
        ip_obj = await create_and_save(
            client=client,
            log=log,
            branch=branch,
            object_name=f"{device_name}-{interface_obj.name.value}-address",
            kind_name="InfraIPAddress",
            data=data,
            store=store,
        )
    return ip_obj

def prepare_interface_data(
        device_obj_id: str,
        intf_name: str,
        intf_role: str,
        intf_status: str,
        description: str,
        account_pop_id: str,
        account_ops_id: str,
        speed: int = 1000,
        l2_mode: str = None,
        mtu: int = None,
        untagged_vlan: Optional[InfrahubNode] = None,
        tagged_vlans: Optional[List[InfrahubNode]] = None,
        ) -> Dict[str, Any]:
    data = {
        "device": {"id": device_obj_id, "is_protected": True},
        "name": {"value": intf_name, "source": account_pop_id, "is_protected": True},
        "description": {"value": description},
        "enabled": True,
        "status": {"value": intf_status, "owner": account_ops_id},
        "role": {"value": intf_role, "source": account_pop_id, "is_protected": True},
        "speed": speed,
        "kind_name": "InfraInterfaceL3" if intf_role in L3_ROLE_MAPPING or intf_role in (LOOPBACK_ROLE, MGMT_ROLE) else  "InfraInterfaceL2",
    }
    if l2_mode:
        data["l2_mode"] = l2_mode
        if untagged_vlan:
            data["untagged_vlan"] = untagged_vlan
        if tagged_vlans:
            data["tagged_vlan"] = tagged_vlans
    if mtu:
        data["mtu"] = mtu
    return data

def remove_interface_prefixes(text: str) -> str:
    parts = text.split(':', 1)
    if len(parts) > 1:
        return parts[1].lstrip()
    else:
        return text

def generate_asn(location_index: int, element_type_index: int, element_index: int) -> int:
    location_index_adjusted = location_index + 1
    element_index_adjusted = (element_index + 1) // 2
    asn = 65000 + (location_index_adjusted * 100) + (element_type_index * 10) + element_index_adjusted
    return asn

async def generate_topology(client: InfrahubClient, log: logging.Logger, branch: str, topology: InfrahubNode, topology_index: int) -> Optional[str]:
     async with client.start_tracking(params={"topology": topology.name.value}) as client:
        topology_name = topology.name.value
        topology_id = topology.id

        if not topology.location.peer:
            log.info(f"{topology_name} is not associated with a Location.")
            return None

        location_id = topology.location.peer.id
        location_shortname = topology.location.peer.shortname.value

        log.debug(f"{topology_name} is assigned to {topology.location.peer.name.value}")

        strategy_id = None
        strategy_underlay = None
        strategy_overlay = None

        if topology.strategy.peer:
            strategy_id = topology.strategy.peer.id
            strategy_underlay = topology.strategy.peer.underlay.value
            strategy_overlay = topology.strategy.peer.overlay.value


        # --------------------------------------------------
        # Preparating some variables for the Location
        # --------------------------------------------------
        account_pop = store.get(key="pop-builder", kind="CoreAccount")
        account_crm = store.get("CRM Synchronization", kind="CoreAccount")
        account_eng = store.get(key="Engineering Team", kind="CoreAccount")
        account_ops = store.get(key="Operation Team", kind="CoreAccount")
        orga_duff = store.get(key="Duff", kind="OrganizationTenant")

        # We are using DUFF Oragnization ASN as "internal" (AS65000)
        internal_as = store.get(key="AS65000", kind="InfraAutonomousSystem")

        locations_vlans = await client.filters(kind="InfraVLAN", location__shortname__value=location_shortname, branch=branch)
        populate_local_store(objects=locations_vlans, key_type="name", store=store)
        vlan_pxe = store.get(key=f"{location_shortname.lower()}_server-pxe", kind="InfraVLAN")
        vlans = await client.filters(kind="InfraVLAN", location__shortname__value=location_shortname, branch=branch)
        vlans_server = []
        for vlan in vlans:
            if vlan.role.value == "server" and vlan.name != f"{location_shortname.lower}_server-pxe":
                vlans_server.append(vlan)
        # Using Prefix role to knwow which network to use. Role to Prefix should help avoid doing this
        locations_subnets = await client.filters(kind="InfraPrefix", location__shortname__value=location_shortname, branch=branch)
        location_external_net = []
        location_technical_net_pool = []
        location_loopback_net_pool = []
        location_loopback_vtep_net_pool = []
        location_mgmt_net_pool = []

        if not locations_subnets:
            log.error(f"{topology.location.peer.name.value} doesn't have any prefixes")
            return None

        for prefix in locations_subnets:
            if prefix.role.value == "management":
                location_mgmt_net_pool.append(prefix)
            elif prefix.role.value == "technical":
                location_technical_net_pool.append(prefix)
            elif prefix.role.value == "loopback":
                location_loopback_net_pool.append(prefix)
            elif prefix.role.value == "loopback-vtep":
                location_loopback_vtep_net_pool.append(prefix)
            elif prefix.role.value == "public":
                location_external_net.append(prefix)

        #   -------------------- Devices Generation --------------------
        #   - Create Devices
        #   - Create Devices Interfaces
        #   - Add IP to external facing L3 Interfaces

        loopback_address_pool = location_loopback_net_pool[0].prefix.value.hosts()
        loopback_vtep_address_pool = location_loopback_vtep_net_pool[0].prefix.value.hosts()
        mgmt_address_pool = location_mgmt_net_pool[0].prefix.value.hosts()
        topology_elements = await client.filters(kind="TopologyPhysicalElement", topology__ids=topology.id, populate_store=True, prefetch_relationships=True)

        batch = await client.create_batch()
        sorted_topology_elements = sorted(topology_elements, key=lambda x: x.device_role.value, reverse=True)
        for elemt_index, topology_element in enumerate(sorted_topology_elements):
            if not topology_element.device_type:
                log.info(f"No device_type for {topology_element.name.value} - Ignored")
                continue
            device_type = await client.get(ids=topology_element.device_type.id, kind="InfraDeviceType")
            if not device_type.platform.id:
                log.info(f"No platform for {device_type.name.value} - Ignored")
                continue
            platform = await client.get(ids=device_type.platform.id, kind="InfraPlatform")
            platform_id = platform.id
            device_role_name = topology_element.device_role.value
            device_type_name = device_type.name.value
            device_mtu = topology_element.mtu.value

            for id in range(1, int(topology_element.quantity.value)+1):
                is_border: bool = topology_element.border.value
                device_name = f"{topology_name}-{device_role_name}{id}"
                if is_border and device_role_name != "spine":
                    device_name = f"{topology_name}-border{device_role_name}{id}"
                # If neither underlay nor overlay are eBGP, we create the device with the "default" ASN
                if not strategy_underlay == "ebgp" and not strategy_overlay == "ebgp":
                    device_asn_id = internal_as.id
                else:
                    element_index = 0 if device_role_name == "spine" else id
                    asn = generate_asn(
                        location_index=topology_index,
                        element_type_index=elemt_index,
                        element_index=element_index,
                    )
                    asn_name  = f"AS{asn}"
                    data_asn = {
                        "name": {"value": asn_name, "source": account_crm.id, "owner": account_pop.id},
                        "asn": {"value": asn, "source": account_crm.id, "owner": account_pop.id},
                        "organization": { "id": orga_duff.id },
                        "description": { "value": f"Private {asn_name} for Duff on device {device_name}"}
                    }
                    asn_obj = await create_and_save(
                        client=client,
                        log=log,
                        branch=branch,
                        object_name=asn_name,
                        kind_name="InfraAutonomousSystem",
                        data=data_asn,
                        store=store,
                        retrieved_on_failure=True
                    )
                    device_asn_id = asn_obj.id
                data_device = {
                    "name": { "value": device_name, "source": account_pop.id, "is_protected": True },
                    "location": { "id": location_id, "source": account_pop.id, "is_protected": True },
                    "status": { "value": ACTIVE_STATUS, "owner": account_ops.id },
                    "device_type": { "id": device_type.id, "source": account_pop.id },
                    "role": { "value": device_role_name, "source": account_pop.id, "is_protected": True, "owner": account_eng.id },
                    "asn": { "id": device_asn_id, "source": account_pop.id, "is_protected": True, "owner": account_eng.id },
                    "platform": { "id": platform_id, "source": account_pop.id, "is_protected": True },
                    "topology": { "id": topology_id, "source": account_pop.id, "is_protected": True },
                }
                device_obj = await create_and_save(
                    client=client,
                    log=log,
                    branch=branch,
                    object_name=device_name,
                    kind_name="InfraDevice",
                    data=data_device,
                    store=store,
                    retrieved_on_failure=True
                    )

                # Add device to groups
                platform_group_name = f"{platform.name.value.lower().split(' ', 1)[0]}_devices"
                platform_group = await client.get(name__value=platform_group_name, kind="CoreStandardGroup")
                await platform_group.members.fetch()
                platform_group.members.add(device_obj.id)
                await platform_group.save()
                log.info(f"- Add {device_name} to {platform_group_name} CoreStandardGroup")
                topology_group = await client.get(name__value=f"{topology_name}_topology", kind="CoreStandardGroup")
                await topology_group.members.fetch()
                topology_group.members.add(device_obj.id)
                await topology_group.save()
                log.info(f"- Add {device_name} to {topology_group} CoreStandardGroup")

                # FIXME  Interface name is not unique, upsert() is not good enough for indempotency. Need constraints
                DEVICE_INTERFACE_OBJS[device_name] = await client.filters(kind="InfraInterfaceL3", device__name__value=device_name, branch=branch)
                DEVICE_INTERFACE_OBJS[device_name] += await client.filters(kind="InfraInterfaceL2", device__name__value=device_name, branch=branch)

                # Loopback Interface
                loopback_name = INTERFACE_LOOP_NAME[device_type_name]
                loopback_description = f"{loopback_name.lower().replace(' ', '')}.{device_name.lower()}"
                loopback_data = prepare_interface_data(
                    device_obj_id=device_obj.id,
                    intf_name=loopback_name,
                    intf_role=LOOPBACK_ROLE,
                    intf_status=ACTIVE_STATUS,
                    description=loopback_description,
                    account_pop_id=account_pop.id,
                    account_ops_id=account_ops.id,
                    mtu=device_mtu,
                    )
                loopback_obj = await upsert_interface(
                    client=client,
                    log=log,
                    branch=branch,
                    device_name=device_name,
                    intf_name=loopback_name,
                    data=loopback_data,
                    store=store
                    )
                ip_loop = f"{str(next(loopback_address_pool))}/32"
                await upsert_ip_address(
                    client=client,
                    log=log,
                    branch=branch,
                    prefix_obj=location_loopback_net_pool[0],
                    device_name=device_name,
                    interface_obj=loopback_obj,
                    description=loopback_description,
                    account_pop_id=account_pop.id,
                    address=ip_loop,
                    store=store,
                    batch=batch
                    )

                # Loopback VTEP Interface
                loopback_vtep_name = INTERFACE_VTEP_NAME[device_type_name]
                loopback_vtep_description = f"{loopback_vtep_name.lower().replace(' ', '')}.{device_name.lower()}"
                loopback_vtep_data = prepare_interface_data(
                    device_obj_id=device_obj.id,
                    intf_name=loopback_vtep_name,
                    intf_role=LOOPBACK_ROLE,
                    intf_status=ACTIVE_STATUS,
                    description=loopback_vtep_description,
                    account_pop_id=account_pop.id,
                    account_ops_id=account_ops.id,
                    mtu=device_mtu,
                    )
                loopback_vtep_obj = await upsert_interface(
                    client=client,
                    log=log,
                    branch=branch,
                    device_name=device_name,
                    intf_name=loopback_vtep_name,
                    data=loopback_vtep_data,
                    store=store
                    )
                ip_loop = f"{str(next(loopback_vtep_address_pool))}/32"
                await upsert_ip_address(
                    client=client,
                    log=log,
                    branch=branch,
                    prefix_obj=location_loopback_vtep_net_pool[0],
                    device_name=device_name,
                    interface_obj=loopback_vtep_obj,
                    description=loopback_vtep_description,
                    account_pop_id=account_pop.id,
                    address=ip_loop,
                    store=store,
                    batch=batch
                    )

                # Management Interface
                mgmt_name = INTERFACE_MGMT_NAME[device_type_name]
                mgmt_description = f"{mgmt_name.lower().replace(' ', '')}.{device_name.lower()}"
                mgmt_data = prepare_interface_data(
                    device_obj_id=device_obj.id,
                    intf_name=mgmt_name,
                    intf_role=MGMT_ROLE,
                    intf_status=ACTIVE_STATUS,
                    description=mgmt_description,
                    account_pop_id=account_pop.id,
                    account_ops_id=account_eng.id,
                    mtu=device_mtu,
                    )
                mgmt_obj = await upsert_interface(
                    client=client,
                    log=log,
                    branch=branch,
                    device_name=device_name,
                    intf_name=mgmt_name,
                    data=mgmt_data,
                    store=store
                    )
                ip_mgmt = f"{str(next(mgmt_address_pool))}/24"
                ip_mgmt_obj = await upsert_ip_address(
                    client=client,
                    log=log,
                    branch=branch,
                    prefix_obj=location_mgmt_net_pool[0],
                    device_name=device_name,
                    interface_obj=mgmt_obj,
                    description=mgmt_description,
                    account_pop_id=account_pop.id,
                    address=ip_mgmt,
                    store=store,
                    )

                # Set Mgmt IP as Primary IP
                device_obj.primary_address = ip_mgmt_obj
                await device_obj.save()
                store.set(key=f"{device_name}", node=device_obj)
                log.info(f"- Set {ip_mgmt} as {device_name} Primary IP")

                if device_role_name.lower() not in ["spine", "leaf"]:
                    continue

                for intf_idx, intf_name in enumerate(DEVICES_INTERFACES[device_type_name]):
                    intf_role = INTERFACE_ROLES_MAPPING[device_role_name.lower()][intf_idx]
                    interface_description = f"{intf_name.lower().replace(' ', '')}.{device_name.lower()}"

                    # L3 Interfaces
                    if intf_role in L3_ROLE_MAPPING:
                        interface_data = prepare_interface_data(
                            device_obj_id=device_obj.id,
                            intf_name=intf_name,
                            intf_role=intf_role,
                            intf_status=PROVISIONING_STATUS,
                            description=interface_description,
                            account_pop_id=account_pop.id,
                            account_ops_id=account_ops.id,
                            mtu=device_mtu,
                            )
                    # L2 Interfaces
                    elif intf_role in L2_ROLE_MAPPING:
                        interface_data = prepare_interface_data(
                            device_obj_id=device_obj.id,
                            intf_name=intf_name,
                            intf_role=intf_role,
                            intf_status=PROVISIONING_STATUS,
                            description=interface_description,
                            account_pop_id=account_pop.id,
                            account_ops_id=account_ops.id,
                            l2_mode="Access",
                            untagged_vlan=vlan_pxe,
                            tagged_vlans=vlans_server,
                            mtu=device_mtu,
                        )
                    interface_obj = await upsert_interface(
                        client=client,
                        log=log,
                        branch=branch,
                        device_name=device_name,
                        intf_name=intf_name,
                        data=interface_data,
                        store=store,
                        batch=batch
                    )
        async for node, _ in batch.execute():
            if node._schema.default_filter:
                accessor = f"{node._schema.default_filter.split('__')[0]}"
                log.info(f"- Created {node._schema.kind} - {getattr(node, accessor).value}")
            else:
                log.info(f"- Created {node}")

        #   -------------------- Connect Spines & Leafs --------------------
        #   - Cabling Spines to Leaf, Leaf to Leaf, Spine to Spine
        #   - Add ico IP to Spines <-> Leafs
        spine_quantity = 0
        leaf_quantity = 0
        border_leaf_quantity = 0
        # spines <-> leaf interfaces
        spine_leaf_interfaces = {}
        leaf_uplink_interfaces = {}
        border_leaf_uplink_interfaces = {}
        # leaf <-> leaf interfaces
        leaf_peer_interfaces = {}
        border_leaf_peer_interfaces = {}
        # spines <-> borderleaf interfaces
        spine_uplink_interfaces = {}

        batch = await client.create_batch()
        for topology_element in topology_elements:
            if not topology_element.device_type:
                log.info(f"No device_type for {topology_element.name.value} - Ignored")
                continue
            device_type = await client.get(id=topology_element.device_type.id, kind="InfraDeviceType", populate_store=True)
            device_role_name = topology_element.device_role.value
            device_type_name = device_type.name.value
            is_border: bool = topology_element.border.value

            if device_role_name == "spine":
                spine_quantity = topology_element.quantity.value
                spine_leaf_interfaces = get_interface_names(device_type=device_type_name, device_role="spine", interface_role="leaf")
                spine_uplink_interfaces = get_interface_names(device_type=device_type_name, device_role="spine", interface_role="uplink")
            elif device_role_name == "leaf":
                if is_border:
                    border_leaf_quantity = topology_element.quantity.value
                    border_leaf_uplink_interfaces =  get_interface_names(device_type=device_type_name, device_role="leaf", interface_role="uplink")
                    border_leaf_peer_interfaces = get_interface_names(device_type=device_type_name, device_role="leaf", interface_role="peer")
                else:
                    leaf_quantity = topology_element.quantity.value
                    leaf_uplink_interfaces = get_interface_names(device_type=device_type_name, device_role="leaf", interface_role="uplink")
                    leaf_peer_interfaces = get_interface_names(device_type=device_type_name, device_role="leaf", interface_role="peer")

        #   ---  Cabling Logic  ---
        #   odd number lf1 uplink port <-> sp1 odd number leaf port
        #   even number lf1 uplink port <-> sp2 odd number leaf port
        #   odd number lf2 uplink port <-> sp1 even number leaf port
        #   even number lf2 uplink port <-> sp2 even number leaf port
        #   odd number lf1 peer port <-> lf2 odd number peer port
        #   even number lf1 peer port <-> lf2 even number peer port

        # Cabling Spines <-> Leaf
        if not spine_leaf_interfaces or not leaf_uplink_interfaces:
            log.error("No 'uplink' interfaces found on leaf or no 'leaf' interfaces on spines")
            return None

        interconnection_subnets = IPv4Network(next(iter(location_technical_net_pool)).prefix.value).subnets(new_prefix=31)

        # Cabling Leaf
        backbone_vrf_obj_id = store.get(key="Backbone", kind="InfraVRF").id
        for leaf_idx in range(1, leaf_quantity + 1):
            if leaf_idx > len(spine_leaf_interfaces):
                log.error(f"The quantity of leaf requested ({leaf_quantity}) is superior to the number of interfaces flagged as 'leaf' ({len(spine_leaf_interfaces)})")
                break
            # Calculate the good interfaces based on the Cabling Logic above
            leaf_pair_num = (leaf_idx + 1) // 2
            if leaf_pair_num == 1:
                if len(spine_leaf_interfaces) < 2:
                    continue
                spine_port = spine_leaf_interfaces[0] if leaf_idx % 2 != 0 else spine_leaf_interfaces[1]
            else:
                offset = (leaf_pair_num - 1) * 2
                if len(spine_leaf_interfaces) < offset + 1 :
                    continue
                spine_port = spine_leaf_interfaces[offset] if leaf_idx % 2 != 0 else spine_leaf_interfaces[offset + 1]

            for spine_idx in range(1, spine_quantity + 1):
                if spine_idx > len(leaf_uplink_interfaces):
                    log.error(f"The quantity of spines requested ({spine_quantity}) is superior to the number of interfaces flagged as 'uplink' ({len(leaf_uplink_interfaces)})")
                    break

                spine_pair_num = (spine_idx + 1) // 2
                if spine_pair_num == 1:
                    if len(leaf_uplink_interfaces) < 2:
                        continue
                    uplink_port = leaf_uplink_interfaces[0] if spine_idx % 2 != 0 else leaf_uplink_interfaces[1]
                else:
                    offset = (spine_pair_num - 1) * 2
                    if len(leaf_uplink_interfaces) < offset + 1 :
                        continue
                    if spine_idx % 2 != 0:
                        uplink_port = leaf_uplink_interfaces[offset]
                    else:
                        uplink_port = leaf_uplink_interfaces[offset + 1]

                # Retrieve interfaces from infrahub (as we create them above) #{topology_name}-{device_role_name}
                intf_spine_obj = await client.get(kind="InfraInterfaceL3", name__value=spine_port, device__name__value=f"{topology_name}-spine{spine_idx}")
                intf_leaf_obj = await client.get(kind="InfraInterfaceL3", name__value=uplink_port, device__name__value=f"{topology_name}-leaf{leaf_idx}")
                # store.get(kind="InfraInterfaceL3", key=f"{topology_name}-leaf{leaf_idx}-{uplink_port}")

                new_spine_intf_description = intf_spine_obj.description.value + f" to {intf_leaf_obj.description.value}"
                spine_ico_ip_description = intf_spine_obj.description.value
                new_leaf_intf_description = intf_leaf_obj.description.value + f" to {intf_spine_obj.description.value}"
                leaf_ico_ip_description = intf_leaf_obj.description.value

                interconnection_subnet = next(interconnection_subnets)
                interconnection_ips = list(interconnection_subnet.hosts())
                spine_ip = f"{str(interconnection_ips[0])}/31"
                leaf_ip = f"{str(interconnection_ips[1])}/31"
                prefix_description = f"{location_shortname.lower()}-ico-{IPv4Network(interconnection_subnet).network_address}"
                data = {
                    "prefix":  {"value": IPv4Network(interconnection_subnet) },
                    "description": {"value": prefix_description},
                    "organization": {"id": orga_duff.id },
                    "location": {"id": location_id },
                    "status": {"value": "active" },
                    "role": {"value": "technical" },
                    "ip_namespace": { "id": backbone_vrf_obj_id }
                }
                prefix_obj = await create_and_save(
                    client=client,
                    log=log,
                    branch=branch,
                    object_name=str(interconnection_subnet),
                    kind_name="InfraPrefix",
                    data=data,
                    store=store
                )

                spine_ip_obj = await upsert_ip_address(
                            client=client,
                            log=log,
                            branch=branch,
                            prefix_obj=prefix_obj,
                            device_name=f"{topology_name}-spine{spine_idx}",
                            interface_obj=intf_spine_obj,
                            description=spine_ico_ip_description,
                            account_pop_id=account_pop.id,
                            address=spine_ip,
                            store=store,
                            )
                leaf_ip_obj = await upsert_ip_address(
                            client=client,
                            log=log,
                            branch=branch,
                            prefix_obj=prefix_obj,
                            device_name=f"{topology_name}-leaf{leaf_idx}",
                            interface_obj=intf_leaf_obj,
                            description=leaf_ico_ip_description,
                            account_pop_id=account_pop.id,
                            address=leaf_ip,
                            store=store,
                            )

                # Delete the other interface.connected_endpoint
                # FIXME if we want to redo the cabling - may need to cleanup the other end first

                # Update Spine interface (description, endpoints, status)
                intf_spine_obj.description.value = new_spine_intf_description
                intf_spine_obj.status.value = ACTIVE_STATUS
                intf_spine_obj.connected_endpoint = intf_leaf_obj
                await intf_spine_obj.save(allow_upsert=True)

                # Delete the other interface.connected_endpoint
                # FIXME if we want to redo the cabling - may need to cleanup the other end first

                # Update Leaf interface (description, endpoints, status)
                intf_leaf_obj.description.value = new_leaf_intf_description
                intf_leaf_obj.status.value  = ACTIVE_STATUS
                intf_leaf_obj.connected_endpoint = intf_spine_obj
                await intf_leaf_obj.save(allow_upsert=True)
                log.info(f"- Connected {topology_name}-leaf{leaf_idx}-{uplink_port} to {topology_name}-spine{spine_idx}-{spine_port}")

                # If Topology underlay is BGP, add BGP Sessions Spines <-> Leaf
                if strategy_underlay == "ebgp":
                    spine_obj = await client.get(kind="InfraDevice", name__value=f"{topology_name}-spine{spine_idx}")
                    leaf_obj = await client.get(kind="InfraDevice", name__value=f"{topology_name}-leaf{leaf_idx}")
                    spine_asn_obj = spine_obj.asn.peer
                    leaf_asn_obj = leaf_obj.asn.peer
                    leaf_pair =  (leaf_idx + 1) // 2
                    spine_bgp_group_name = f"{topology_name}-underlay-spine-leaf-pair{leaf_pair}"
                    leaf_bgp_group_name = f"{topology_name}-underlay-leaf-pair{leaf_pair}-spine"
                    data_spine_bgp_group = {
                        "name": { "value": spine_bgp_group_name},
                        "local_as": { "id": spine_asn_obj.id},
                        "remote_as": { "id": leaf_asn_obj.id},
                        "description": {"value": f"BGP group for {topology_name} underlay" },
                    }
                    spine_bgp_group_obj = await create_and_save(
                        client=client,
                        log=log,
                        branch=branch,
                        object_name=f"bgpgroup-underlay-{spine_obj.name.value}-{leaf_obj.name.value}",
                        kind_name="InfraBGPPeerGroup",
                        data=data_spine_bgp_group,
                        store=store,
                    )
                    data_leaf_bgp_group = {
                        "name": { "value": leaf_bgp_group_name},
                        "remote_as": { "id": spine_asn_obj.id},
                        "local_as": { "id": leaf_asn_obj.id},
                        "description": {"value": f"BGP group for {topology_name} underlay" },
                    }
                    leaf_bgp_group_obj = await create_and_save(
                        client=client,
                        log=log,
                        branch=branch,
                        object_name=f"bgpgroup-underlay-{leaf_obj.name.value}-{spine_obj.name.value}",
                        kind_name="InfraBGPPeerGroup",
                        data=data_leaf_bgp_group,
                        store=store,
                    )
                    data_spine_session = {
                        "local_as": { "id": spine_asn_obj.id},
                        "remote_as": { "id": leaf_asn_obj.id},
                        "local_ip": { "id": spine_ip_obj.id},
                        "remote_ip": { "id": leaf_ip_obj.id},
                        "type": { "value": "EXTERNAL"},
                        "status": { "value": ACTIVE_STATUS},
                        "role": { "value": "backbone"},
                        "device": { "id": spine_obj.id },
                        "peer_group": { "id": spine_bgp_group_obj.id },
                        "description": {"value": remove_interface_prefixes(new_spine_intf_description) },
                    }
                    spine_session_obj = await create_and_save(
                        client=client,
                        log=log,
                        branch=branch,
                        object_name=f"spine-{str(interconnection_subnet)}",
                        kind_name="InfraBGPSession",
                        data=data_spine_session,
                        store=store,
                    )
                    data_leaf_session = {
                        "remote_as": { "id": spine_asn_obj.id},
                        "local_as": { "id": leaf_asn_obj.id},
                        "remote_ip": { "id": spine_ip_obj.id},
                        "local_ip": { "id": leaf_ip_obj.id},
                        "type": { "value": "EXTERNAL"},
                        "status": { "value": ACTIVE_STATUS},
                        "role": { "value": "backbone"},
                        "device": { "id": leaf_obj.id },
                        "peer_session": { "id": spine_session_obj.id },
                        "peer_group": { "id": leaf_bgp_group_obj.id },
                        "description": {"value": remove_interface_prefixes(new_leaf_intf_description) },
                    }
                    leaf_session_obj = await create_and_add_to_batch(
                        client=client,
                        log=log,
                        branch=branch,
                        object_name=f"leaf-{str(interconnection_subnet)}",
                        kind_name="InfraBGPSession",
                        data=data_leaf_session,
                        store=store,
                        batch=batch
                    )

        # Cabling BorderLeaf
        if border_leaf_quantity > 0:
            for leaf_idx in range(1, border_leaf_quantity + 1):
                if leaf_idx > len(spine_uplink_interfaces):
                    log.error(f"The quantity of borderleaf requested ({border_leaf_quantity}) is superior to the number of interfaces flagged as 'uplink' ({len(spine_uplink_interfaces)})")
                    break
                # Calculate the good interfaces based on the Cabling Logic above
                leaf_pair_num = (leaf_idx + 1) // 2
                if leaf_pair_num == 1:
                    if len(spine_uplink_interfaces) < 2:
                        continue
                    spine_port = spine_uplink_interfaces[0] if leaf_idx % 2 != 0 else spine_uplink_interfaces[1]
                else:
                    offset = (leaf_pair_num - 1) * 2
                    if len(spine_uplink_interfaces) < offset + 1 :
                        continue
                    spine_port = spine_uplink_interfaces[offset] if leaf_idx % 2 != 0 else spine_uplink_interfaces[offset + 1]

                for spine_idx in range(1, spine_quantity + 1):
                    if spine_idx > len(border_leaf_uplink_interfaces):
                        log.error(f"The quantity of spines requested ({spine_quantity}) is superior to the number of interfaces flagged as 'uplink' ({len(border_leaf_uplink_interfaces)})")
                        break

                    spine_pair_num = (spine_idx + 1) // 2
                    if spine_pair_num == 1:
                        if len(border_leaf_uplink_interfaces) < 2:
                            continue
                        leaf_port = border_leaf_uplink_interfaces[0] if spine_idx % 2 != 0 else border_leaf_uplink_interfaces[1]
                    else:
                        offset = (spine_pair_num - 1) * 2
                        if len(border_leaf_uplink_interfaces) < offset + 1 :
                            continue
                        if spine_idx % 2 != 0:
                            leaf_port = border_leaf_uplink_interfaces[offset]
                        else:
                            leaf_port = border_leaf_uplink_interfaces[offset + 1]

                    # Retrieve interfaces from infrahub (as we create them above) #{topology_name}-{device_role_name}
                    intf_spine_obj = await client.get(kind="InfraInterfaceL3", name__value=spine_port, device__name__value=f"{topology_name}-spine{spine_idx}")
                    intf_leaf_obj = await client.get(kind="InfraInterfaceL3", name__value=leaf_port, device__name__value=f"{topology_name}-borderleaf{leaf_idx}")
                    # store.get(kind="InfraInterfaceL3", key=f"{topology_name}-borderleaf{leaf_idx}-{leaf_port}")

                    new_spine_intf_description = intf_spine_obj.description.value + f" to {intf_leaf_obj.description.value}"
                    spine_ico_ip_description = intf_spine_obj.description.value
                    new_leaf_intf_description = intf_leaf_obj.description.value + f" to {intf_spine_obj.description.value}"
                    leaf_ico_ip_description = intf_leaf_obj.description.value

                    interconnection_subnet = next(interconnection_subnets)
                    interconnection_ips = list(interconnection_subnet.hosts())
                    spine_ip = f"{str(interconnection_ips[0])}/31"
                    leaf_ip = f"{str(interconnection_ips[1])}/31"
                    prefix_description = f"{location_shortname.lower()}-ico-{IPv4Network(interconnection_subnet).network_address}"
                    data = {
                        "prefix":  {"value": IPv4Network(interconnection_subnet) },
                        "description": {"value": prefix_description},
                        "organization": {"id": orga_duff.id },
                        "location": {"id": location_id },
                        "status": {"value": "active"},
                        "role": {"value": "technical"},
                        "ip_namespace": { "id": backbone_vrf_obj_id }
                    }
                    prefix_obj = await create_and_save(
                        client=client,
                        log=log,
                        branch=branch,
                        object_name=str(interconnection_subnet),
                        kind_name="InfraPrefix",
                        data=data,
                        store=store
                    )

                    spine_ip_obj = await upsert_ip_address(
                                client=client,
                                log=log,
                                branch=branch,
                                prefix_obj=prefix_obj,
                                device_name=f"{topology_name}-spine{spine_idx}",
                                interface_obj=intf_spine_obj,
                                description=spine_ico_ip_description,
                                account_pop_id=account_pop.id,
                                address=spine_ip,
                                store=store,
                                )
                    leaf_ip_obj = await upsert_ip_address(
                                client=client,
                                log=log,
                                branch=branch,
                                prefix_obj=prefix_obj,
                                device_name=f"{topology_name}-borderleaf{leaf_idx}",
                                interface_obj=intf_leaf_obj,
                                description=leaf_ico_ip_description,
                                account_pop_id=account_pop.id,
                                address=leaf_ip,
                                store=store,
                                )

                    # Delete the other interface.connected_endpoint
                    # FIXME if we want to redo the cabling - may need to cleanup the other end first

                    # Update Spine interface (description, endpoints, status)
                    intf_spine_obj.description.value = new_spine_intf_description
                    intf_spine_obj.status.value = ACTIVE_STATUS
                    intf_spine_obj.connected_endpoint = intf_leaf_obj
                    await intf_spine_obj.save(allow_upsert=True)

                    # Delete the other interface.connected_endpoint
                    # FIXME if we want to redo the cabling - may need to cleanup the other end first

                    # Update Leaf interface (description, endpoints, status)
                    intf_leaf_obj.description.value = new_leaf_intf_description
                    intf_leaf_obj.status.value  = ACTIVE_STATUS
                    intf_leaf_obj.connected_endpoint = intf_spine_obj
                    await intf_leaf_obj.save(allow_upsert=True)
                    log.info(f"- Connected {topology_name}-leaf{leaf_idx}-{uplink_port} to {topology_name}-spine{spine_idx}-{spine_port}")

                    # If Topology underlay is BGP, add BGP Sessions Spines <-> Leaf
                    if strategy_underlay == "ebgp":
                        spine_obj = await client.get(kind="InfraDevice", name__value=f"{topology_name}-spine{spine_idx}")
                        leaf_obj = await client.get(kind="InfraDevice", name__value=f"{topology_name}-borderleaf{leaf_idx}")
                        spine_asn_obj = spine_obj.asn.peer
                        leaf_asn_obj = leaf_obj.asn.peer
                        leaf_pair =  (leaf_idx + 1) // 2
                        spine_bgp_group_name = f"{topology_name}-underlay-spine-borderleaf-pair{leaf_pair}"
                        leaf_bgp_group_name = f"{topology_name}-underlay-borderleaf-pair{leaf_pair}-spine"
                        data_spine_bgp_group = {
                            "name": { "value": spine_bgp_group_name},
                            "local_as": { "id": spine_asn_obj.id},
                            "remote_as": { "id": leaf_asn_obj.id},
                            "description": {"value": f"BGP group for {topology_name} underlay" },
                        }
                        spine_bgp_group_obj = await create_and_save(
                            client=client,
                            log=log,
                            branch=branch,
                            object_name=f"bgpgroup-underlay-{spine_obj.name.value}-{leaf_obj.name.value}",
                            kind_name="InfraBGPPeerGroup",
                            data=data_spine_bgp_group,
                            store=store,
                        )
                        data_leaf_bgp_group = {
                            "name": { "value": leaf_bgp_group_name},
                            "remote_as": { "id": spine_asn_obj.id},
                            "local_as": { "id": leaf_asn_obj.id},
                            "description": {"value": f"BGP group for {topology_name} underlay" },
                        }
                        leaf_bgp_group_obj = await create_and_save(
                            client=client,
                            log=log,
                            branch=branch,
                            object_name=f"bgpgroup-underlay-{leaf_obj.name.value}-{spine_obj.name.value}",
                            kind_name="InfraBGPPeerGroup",
                            data=data_leaf_bgp_group,
                            store=store,
                        )
                        data_spine_session = {
                            "local_as": { "id": spine_asn_obj.id},
                            "remote_as": { "id": leaf_asn_obj.id},
                            "local_ip": { "id": spine_ip_obj.id},
                            "remote_ip": { "id": leaf_ip_obj.id},
                            "type": { "value": "EXTERNAL"},
                            "status": { "value": ACTIVE_STATUS},
                            "role": { "value": "backbone"},
                            "device": { "id": spine_obj.id },
                            "peer_group": { "id": spine_bgp_group_obj.id },
                            "description": {"value": remove_interface_prefixes(new_spine_intf_description) },
                        }
                        spine_session_obj = await create_and_save(
                            client=client,
                            log=log,
                            branch=branch,
                            object_name=f"spine-{str(interconnection_subnet)}",
                            kind_name="InfraBGPSession",
                            data=data_spine_session,
                            store=store,
                        )
                        data_leaf_session = {
                            "remote_as": { "id": spine_asn_obj.id},
                            "local_as": { "id": leaf_asn_obj.id},
                            "remote_ip": { "id": spine_ip_obj.id},
                            "local_ip": { "id": leaf_ip_obj.id},
                            "type": { "value": "EXTERNAL"},
                            "status": { "value": ACTIVE_STATUS},
                            "role": { "value": "backbone"},
                            "device": { "id": leaf_obj.id },
                            "peer_session": { "id": spine_session_obj.id },
                            "peer_group": { "id": leaf_bgp_group_obj.id },
                            "description": {"value": remove_interface_prefixes(new_leaf_intf_description) },
                        }
                        leaf_session_obj = await create_and_save(
                            client=client,
                            log=log,
                            branch=branch,
                            object_name=f"borderleaf-{str(interconnection_subnet)}",
                            kind_name="InfraBGPSession",
                            data=data_leaf_session,
                            store=store,
                            batch=batch
                        )

        # Cabling Leaf <-> Leaf
        if not leaf_peer_interfaces:
            log.error("No 'peer' interfaces found on Leaf")
            return None

        if leaf_quantity % 2 != 0:
            log.error("The number of leaf must be even to form pairs")
            return None

        for leaf_idx in range(1, leaf_quantity + 1, 2):
            leaf1_name = f"{topology_name}-leaf{leaf_idx}"
            leaf2_name = f"{topology_name}-leaf{leaf_idx + 1}"
            for leaf_peer_interface in leaf_peer_interfaces:
                intf_leaf1_obj = store.get(kind="InfraInterfaceL3", key=f"{leaf1_name}-{leaf_peer_interface}")
                intf_leaf2_obj = store.get(kind="InfraInterfaceL3", key=f"{leaf2_name}-{leaf_peer_interface}")

                new_leaf1_intf_description = intf_leaf1_obj.description.value + f" to {intf_leaf2_obj.description.value}"
                new_leaf2_intf_description = intf_leaf2_obj.description.value + f" to {intf_leaf1_obj.description.value}"

                # Update Leaf1 interface (description, endpoints, status)
                intf_leaf1_obj.description.value = new_leaf1_intf_description
                intf_leaf1_obj.status.value = ACTIVE_STATUS
                intf_leaf1_obj.connected_endpoint = intf_leaf2_obj
                await intf_leaf1_obj.save()
                # Update Leaf2 interface (description, endpoints, status)
                intf_leaf2_obj.description.value = new_leaf2_intf_description
                intf_leaf2_obj.status.value = ACTIVE_STATUS
                intf_leaf2_obj.connected_endpoint = intf_leaf1_obj
                await intf_leaf2_obj.save()

        async for node, _ in batch.execute():
            if node._schema.default_filter:
                accessor = f"{node._schema.default_filter.split('__')[0]}"
                log.info(f"- Created {node._schema.kind} - {getattr(node, accessor).value}")
            else:
                log.info(f"- Created {node}")

        #   -------------------- Overlay Spines & Leafs --------------------
        #   - eBGP Sessions within the Site (Spines <-> Spines, Spines <-> Leaf)
        # TODO
        if strategy_overlay == "ebgp":
            # TODO get loopback ip for all devices
            # create BGP peer group "per" device ?
            pass

        #   -------------------- Forcing the Generation of the Artifact --------------------
        artifact_definitions = await client.filters(kind="CoreArtifactDefinition")
        for artifact_definition in artifact_definitions:
            await artifact_definition.generate()

        return location_shortname

# ---------------------------------------------------------------
# Use the `infrahubctl run` command line to execute this script
#
#   infrahubctl run models/infrastructure_edge.py
#
# ---------------------------------------------------------------
async def run(client: InfrahubClient, log: logging.Logger, branch: str, **kwargs) -> None:
    # ------------------------------------------
    # Retrieving objects from Infrahub
    # ------------------------------------------
    log.info("Retrieving objects from Infrahub")
    try:
        # CoreAccount
        accounts=await client.all("CoreAccount")
        populate_local_store(objects=accounts, key_type="name", store=store)
        # Organizations
        tenants=await client.all("OrganizationTenant")
        populate_local_store(objects=tenants, key_type="name", store=store)
        providers=await client.all("OrganizationProvider")
        populate_local_store(objects=providers, key_type="name", store=store)
        manufacturers=await client.all("OrganizationManufacturer")
        populate_local_store(objects=manufacturers, key_type="name", store=store)
        # ASN
        autonomous_systems=await client.all("InfraAutonomousSystem")
        populate_local_store(objects=autonomous_systems, key_type="name", store=store)
        # Platforms + Device Types
        platforms=await client.all("InfraPlatform")
        populate_local_store(objects=platforms, key_type="name", store=store)
        device_types=await client.all("InfraDeviceType")
        populate_local_store(objects=device_types, key_type="name", store=store)
        # Topologies + Network Strategies
        topologies=await client.all("TopologyTopology")
        populate_local_store(objects=topologies, key_type="name", store=store)
        evpn_strategies=await client.all("TopologyEVPNStrategy", populate_store=True)
        populate_local_store(objects=evpn_strategies, key_type="name", store=store)
        # Locations
        locations=await client.all("LocationGeneric", populate_store=True)
        populate_local_store(objects=locations, key_type="name", store=store)
        # Groups
        groups=await client.all("CoreStandardGroup")
        populate_local_store(objects=groups, key_type="name", store=store)
        # Prefixes
        prefixes=await client.all("InfraPrefix")
        populate_local_store(objects=prefixes, key_type="prefix", store=store)
        # VRF
        vrfs=await client.all("InfraVRF")
        populate_local_store(objects=vrfs, key_type="name", store=store)

    except Exception as e:
        log.error(f"Fail to populate due to {e}")
        exit(1)

    log.info("Adding a new Device Role (client) via the SDK")
    try:
        await client.schema.add_dropdown_option(
            kind="InfraDevice",
            attribute="role",
            option="client",
            color="#c5a3ff",
            description="Server & Client endpoints."
        )
    except Exception as e:
        log.debug(f"Fail to add Client dropdown option due to {e}")

    # ------------------------------------------
    # Create Topology
    # ------------------------------------------
    topology_name= None
    if "topology" in kwargs:
        topology_name = kwargs["topology"]
    if not topology_name:
        log.info("Generation Topologies")
    batch = await client.create_batch()
    for index, topology in enumerate(topologies):
        try:
            location_peer = topology.location.peer
            if topology_name and not topology.name.value == topology_name:
                continue

            log.info(f"Generation topology {topology.name.value}")
            batch.add(
                task=generate_topology,
                topology=topology,
                client=client,
                branch=branch,
                log=log,
                topology_index=index,
                node=topology,
                )
        except ValueError:
            # You should end-up here if topology.location.peer is not set
            continue

    if batch.num_tasks < 1:
        if topology_name:
            log.info(f"{topology_name} doesn't exist or is not associated with a site")
        else:
            log.info(f"No Topologies found")
    else:
        async for node, _ in batch.execute():
            accessor = f"{node._schema.default_filter.split('__')[0]}"
            log.info(f"- Created {node._schema.kind} - {getattr(node, accessor).value}")
