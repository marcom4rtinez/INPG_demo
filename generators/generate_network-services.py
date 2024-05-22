import logging

from ipaddress import IPv4Network
from typing import Any, Dict, List, Optional

from infrahub_sdk import InfrahubBatch, InfrahubClient, InfrahubNode, NodeStore

from utils import create_and_save, populate_local_store


# flake8: noqa
# pylint: skip-file


# Mapping Dropdown Role and Status here
ACTIVE_STATUS = "active"
PROVISIONING_STATUS = "provisioning"

store = NodeStore()
async def generate_network_services(
        client: InfrahubClient,
        log: logging.Logger,
        branch: str,
        topology: InfrahubNode,
        vrf: InfrahubNode,
        service_type: str,
        topology_index: int,
        vrf_index: int,
        service_id: int,
    ) -> Optional[str]:

    account_pop = store.get(key="pop-builder", kind="CoreAccount")
    account_eng = store.get(key="Engineering Team", kind="CoreAccount")
    account_ops = store.get(key="Operation Team", kind="CoreAccount")
    orga_duff_obj = store.get(key="Duff", kind="OrganizationTenant")

    # TODO get the `type` options from the networkservices schema
    if service_type.title() not in ("Layer2", "Layer3"):
        log.error(f"{service_type.title()} is not a supported service type options.")
        return None

    if not topology.location.peer:
        log.error(f"{topology_name} is not associated with a Location.")
        return None

    vrf_name = vrf.name.value
    vrf_id = vrf.id
    topology_id = topology.id
    topology_name = topology.name.value
    location_id = topology.location.peer.id
    location_name = topology.location.peer.name.value
    location_shortname = topology.location.peer.shortname.value
    locations_subnets = await client.filters(kind="InfraPrefix", location__ids=[location_id], branch=branch, populate_store=True)

    #   ---  Network Services Logic  ---
    #
    #   Prefix - 253 x /24 per Site
    #       - used the supernet of the Location (Building)
    #
    #   VLAN - 9 VRF + 100 Services per VRF
    #       - used the vlans associated with the Location (Building)
    #       - Abritary using 1YZZ
    #           - Y = VRF index
    #           - ZZ = sevices reference
    #
    #   Service Identifier - 100 per VRF per Site
    #       - Abritary at 4 digit, as XYZZ
    #           - X = Site index
    #           - Y = VRF index
    #           - ZZ = sevices reference

    location_supernet = None
    remaining_prefixes = []
    existing_prefixes = 0
    for locations_subnet in locations_subnets:
        if locations_subnet.role.value == "supernet":
            location_supernet = locations_subnet
            break
    if service_type.title() == "Layer3":
        if not location_supernet:
            log.error(f"{topology.location.peer.name.value} doesn't have any supernet, we are not able to define which prefixes we can used.")
            return None
    # FIXME
    # Replace Section when we have Ressource Manager
        else:
            for locations_subnet in locations_subnets:
                if locations_subnet.role.value in ("server"):
                    existing_prefixes += 1
            all_prefixes = list(IPv4Network(location_supernet.prefix.value).subnets(new_prefix=24))
            remaining_prefixes = all_prefixes[existing_prefixes:]
            if len(remaining_prefixes) < 4:
                log.error(f"The number of prefixes still available in {location_supernet.prefix.value} doesn't allow to create the requested services")
                return None
    locations_vlans = await client.filters(kind="InfraVLAN", location__ids=[location_id], branch=branch, populate_store=True)
    vlan_prefix_to_match = int(f"1{vrf_index}")
    existing_vlans = [location_vlan for location_vlan in locations_vlans if location_vlan.role.value == "server" and location_vlan.vlan_id.value // 100 == vlan_prefix_to_match ]
    service_identifiers = await client.filters(kind="TopologyNetworkServiceIdentifier", branch=branch, populate_store=True)
    identifier_prefix_to_match = int(f"{topology_index}{vrf_index}")
    existing_services = [identifier for identifier in service_identifiers if int(identifier.identifier.value) // 100 == identifier_prefix_to_match]

    # Debug helper
    log.debug(f"Number of existing Prefixes = {existing_prefixes}")
    log.debug(f"Number of existing Vlans = {len(existing_vlans)}")
    log.debug(f"Number of existing Services = {len(existing_services)}")

    new_service_id = service_id if service_id else identifier_prefix_to_match * 100 + len(existing_services) + 1
    params = {
        "service_id": new_service_id,
    }
    previous_vlan_id = 0
    previous_prefix = None
    previous_service_name = None
    previous_service_obj = None
    if service_id :
        client.set_context_properties(identifier=client.identifier, params=params)
        group = await client.group_context.get_group(store_peers=True)
        if group:
            if client.group_context.previous_members:
                for member in client.group_context.previous_members:
                    obj = client.store.get(kind=member._typename, key=member.id)
                    if member._typename == "InfraVLAN":
                        previous_vlan_id = obj.vlan_id.value
                    elif member._typename == "InfraPrefix":
                        previous_prefix = obj.prefix.value
                    elif member._typename == "TopologyNetworkService":
                        previous_service_name = obj.name.value
                        previous_service_obj = obj

    vlan_id = previous_vlan_id if previous_vlan_id > 0 else vlan_prefix_to_match * 100 + len(existing_vlans) + 1
    vlan_name = f"{location_shortname.lower()}_{str(vlan_id)}"
    service_prefix = "l2"
    if service_type.title() == "Layer3":
        service_prefix = "l3"
    service_name = previous_service_name if previous_service_name and previous_service_name.startswith(service_prefix) else service_prefix + '_server_' + str(new_service_id)
    service_description = f"{service_prefix.upper()} Service in {vrf_name} VRF on {topology_name}"

    async with client.start_tracking(params=params, delete_unused_nodes=True) as client:
        # Create VLAN
        vlan_data = {
            "name": { "value": vlan_name, "is_protected": True, "source": account_pop.id },
            "vlan_id": { "value": vlan_id, "is_protected": True, "owner": account_eng.id, "source": account_pop.id },
            "description": { "value": f"{location_name.upper()} - {vlan_name.lower()} VLAN" },
            "status": { "value": ACTIVE_STATUS, "owner": account_ops.id },
            "role": { "value": "server", "source": account_pop.id, "is_protected": True, "owner": account_eng.id },
            "location": { "id": location_id},
        }
        vlan_obj = await create_and_save(
            client=client,
            log=log,
            branch=branch,
            object_name=vlan_name,
            kind_name="InfraVLAN",
            data=vlan_data,
            store=store,
            retrieved_on_failure=True
            )
        # Create Prefix
        prefix_obj = None
        if service_type.title() == "Layer3":
            prefix_prefix = previous_prefix if previous_prefix else remaining_prefixes[1]
            prefix_description = f"{location_shortname.lower()}-server-{IPv4Network(prefix_prefix).network_address}"
            prefix_data = {
                "prefix": { "value": prefix_prefix, "is_protected": True, "source": account_pop.id },
                "description": { "value": prefix_description},
                "organization": { "id": orga_duff_obj.id },
                "location": { "id": location_id },
                "status": { "value": "active" },
                "role": { "value": "server" },
                "ip_namespace": { "id": vrf_id },
            }
            prefix_obj = await create_and_save(
                client=client,
                log=log,
                branch=branch,
                object_name=prefix_prefix,
                kind_name="InfraPrefix",
                data=prefix_data,
                store=store,
                retrieved_on_failure=True
                )
        # Create Service Identifier
        identifier_data = {
            "identifier": {"value": new_service_id, "is_protected": True, "source": account_pop.id},
        }
        identifier_obj = await create_and_save(
            client=client,
            log=log,
            branch=branch,
            object_name=new_service_id,
            kind_name="TopologyNetworkServiceIdentifier",
            data=identifier_data,
            store=store,
            retrieved_on_failure=True
            )
        # Create Service
        vlan_obj_id = vlan_obj.id
        identifier_obj_id = identifier_obj.id
        prefix_obj_id = None
        if prefix_obj:
            prefix_obj_id = prefix_obj.id
        service_data = {
            "name": { "value": service_name, "is_protected": True, "source": account_pop.id},
            "description": { "value": service_description, "is_protected": True, "source": account_pop.id},
            "service_type": { "value": service_type.title(), "is_protected": True, "source": account_pop.id},
            "vlan": { "id": vlan_obj_id, "is_protected": True, "source": account_pop.id},
            "identifier": { "id": identifier_obj_id, "is_protected": True, "source": account_pop.id},
            "prefix": { "id": prefix_obj_id, "is_protected": True, "source": account_pop.id},
            "topology": { "id": topology_id }
        }
        if previous_service_obj:
            service_data["id"] = previous_service_obj.id
        service_obj = await create_and_save(
                client=client,
                log=log,
                branch=branch,
                object_name=service_name,
                kind_name="TopologyNetworkService",
                data=service_data,
                store=store,
                )
    #   -------------------- Forcing the Generation of the Artifact --------------------
    artifact_definitions = await client.filters(kind="CoreArtifactDefinition")
    for artifact_definition in artifact_definitions:
        await artifact_definition.generate()

    if service_obj:
        # Add the new vlan for all the L2 interface of the topology
        return service_obj.id
    else:
        return None

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
        # Topologies + Related informations
        topologies=await client.all("TopologyTopology", populate_store=True, prefetch_relationships=True)
        populate_local_store(objects=topologies, key_type="name", store=store)
        # VRF
        vrfs=await client.all("InfraVRF")
        populate_local_store(objects=vrfs, key_type="name", store=store)
        # TopologyNetworkService
        services=await client.all("TopologyNetworkService", populate_store=True)
        populate_local_store(objects=services, key_type="name", store=store)

    except Exception as e:
        log.error(f"Fail to populate due to {e}")
        exit(1)

    # ------------------------------------------
    # Create Network Services
    # ------------------------------------------
    service_id = 0
    service_type = "Layer2"
    vrf_name = "staging"

    if "vrf" in kwargs:
        vrf_name = kwargs["vrf"]
    if "topology" in kwargs:
        topology_name = kwargs["topology"]
    if "type" in kwargs:
        service_type = kwargs["type"]
    if "id" in kwargs:
        service_id = int(kwargs["id"])

    vrf_obj = None
    topology_obj = None
    topology_index = -1
    vrf_index = -1
    if not topology_name:
        log.info("No topologies indicated, action cancelled")
        exit(0)
    for index, topology in enumerate(topologies):
        if topology.name.value != topology_name.lower():
            continue
        topology_obj = topology
        topology_index = index
    for index, vrf in enumerate(vrfs):
        if vrf.name.value != vrf_name.title():
            continue
        vrf_obj = vrf
        vrf_index = index

    if not topology_obj or not vrf_obj:
        log.info("Could not find the topology or the vrf, action cancelled")
        exit(0)

    batch = await client.create_batch()
    if not service_id:
        log.info(f"Generation of a {service_type.title()} services in {vrf_name.title()} VRF on {topology_name}")
    else:
        log.info(f"Creating or updating {service_id} based on the others parameters given")
    await generate_network_services(
        client=client,
        branch=branch,
        log=log,
        service_type=service_type,
        topology=topology_obj,
        vrf=vrf_obj,
        topology_index=topology_index+1,
        vrf_index = vrf_index+1,
        service_id=service_id,
    )
    if not service_id:
        log.info(f"Created new {service_type.title()} services in {vrf_name.title()} VRF on {topology_name}")
    else:
        log.info(f"Created or updated {service_id}")
