import logging
import uuid
import random
from collections import defaultdict
from ipaddress import IPv4Network
from typing import Dict, List

from infrahub_sdk import UUIDT, InfrahubClient, InfrahubNode, NodeStore

from utils import create_and_save, create_and_add_to_batch, populate_local_store

# flake8: noqa
# pylint: skip-file

LOCATIONS = {
    "Europe": {
        "shortname": "EU",
        "timezone": "GMT+1",
        "countries": {
            "Germany": {
                "shortname": "DE",
                "timezone": "CET",
                "regions": {
                    "de-central": {
                        "shortname": "DECN",
                        "metros": {
                            "Frankfurt": {
                                "shortname": "FRA",
                                "buildings": {
                                    "Equinix FRA05": {
                                        "shortname": "FRA05",
                                        "facility_id": "eqx-fra05",
                                        "owner": "Equinix",
                                        "floors": {
                                            "floor-32": {
                                                "shortname": "F32",
                                                "suites": {
                                                    "suite-325": {
                                                        "shortname": "S325",
                                                        "facility_id": "F32S5",
                                                        "owner": "Equinix",
                                                        "racks": {
                                                            "Rack-05": {
                                                                "facility_id": "F33S5R05",
                                                                "owner": "Duff"
                                                            },
                                                        }
                                                    }
                                                }
                                            },
                                            "floor-33": {
                                                "shortname": "F33",
                                                "suites": {
                                                    "suite-338": {
                                                        "shortname": "S338",
                                                        "facility_id": "F33S8",
                                                        "owner": "Equinix",
                                                        "racks": {
                                                            "Rack-09": {
                                                                "facility_id": "F33S8R09",
                                                                "owner": "Duff"
                                                            },
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "Netherlands": {
                "shortname": "NL",
                "timezone": "CET",
                "regions": {
                    "nl-west": {
                        "shortname": "NLW",
                        "metros": {
                            "Amsterdam": {
                                "shortname": "AMS",
                                "buildings": {
                                    "Interxion AMS9": {
                                        "shortname": "AMS9",
                                        "facility_id": "ITX-AMS9",
                                        "owner": "Interxion",
                                        "floors": {
                                            "floor-0": {
                                                "shortname": "F0",
                                                "suites": {
                                                    "suite-ld8-596": {
                                                        "shortname": "LD8",
                                                        "facility_id": "00-ld8-596",
                                                        "owner": "Duff",
                                                        "racks": {
                                                            "R01B01": {
                                                                "facility_id": "LD8-596-R01B01",
                                                            },
                                                            "R01B02": {
                                                                "facility_id": "LD8-596-R01B02",
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    "North America": {
        "shortname": "NA",
        "countries": {
            "United States of America": {
                "shortname": "USA",
                "regions": {
                    "us-east": {
                        "shortname": "USE",
                        "timezone": "EST",
                        "metros": {
                            "Atlanta": {"shortname": "ATL"},
                            "south": {"shortname": "SO"}
                        }
                    },
                    "us-central": {
                        "shortname": "USC",
                        "timezone": "CST",
                        "metros": {
                            "Denver": {
                                "shortname": "DEN",
                                "buildings": {
                                    "Equinix DE1": {
                                        "shortname": "DE1",
                                        "facility_id": "eqx-de1",
                                        "owner": "Equinix",
                                        "floors": {
                                            "floor-11": {
                                                "shortname": "F11",
                                                "suites": {
                                                    "suite-111": {
                                                        "shortname": "S111",
                                                        "facility_id": "F11S1",
                                                        "owner": "Equinix",
                                                        "racks": {
                                                            "Rack-1111": {
                                                                "facility_id": "F11S1R01",
                                                                "owner": "Duff",
                                                            }
                                                        }
                                                    },
                                                    "suite-112": {
                                                        "shortname": "S112",
                                                        "facility_id": "F11S2",
                                                        "owner": "Equinix",
                                                        "racks": {
                                                            "Rack-1121": {
                                                                "facility_id": "F11S2R01",
                                                                "owner": "Duff",
                                                            }
                                                        }
                                                    }
                                                }
                                            },
                                            "floor-12": {
                                                "shortname": "F12",
                                                "suites": {
                                                    "suite-121": {
                                                        "shortname": "S121",
                                                        "facility_id": "F12S1",
                                                        "owner": "Equinix",
                                                        "racks": {
                                                            "Rack-1211": {
                                                                "facility_id": "F12S1R01",
                                                                "owner": "Duff",
                                                            },
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    },
                                    "Equinix DE2": {
                                        "shortname": "DE2",
                                        "facility_id": "eqx-de2",
                                        "owner": "Equinix",
                                        "floors": {
                                            "floor-21": {
                                                "shortname": "F21",
                                                "suites": {
                                                    "suite-211": {
                                                        "shortname": "S211",
                                                        "facility_id": "F21S1",
                                                        "owner": "Equinix",
                                                        "racks": {
                                                            "Rack-21211": {
                                                                "facility_id": "F21S1R11",
                                                                "owner": "Duff"
                                                            },
                                                        }
                                                    },
                                                    "suite-212": {
                                                        "shortname": "S212",
                                                        "facility_id": "F21S2",
                                                        "owner": "Equinix",
                                                        "racks": {
                                                            "Rack-21210": {
                                                                "facility_id": "F21S2R10",
                                                                "owner": "Duff",
                                                            },
                                                        }
                                                    }
                                                }
                                            },
                                            "floor-22": {
                                                "shortname": "F22",
                                                "suites": {
                                                    "suite-221": {
                                                        "shortname": "S221",
                                                        "facility_id": "F22S1",
                                                        "owner": "Duff",
                                                        "racks": {
                                                            "Rack-22105": {
                                                                "facility_id": "F22S1R05",
                                                            },
                                                            "Rack-22106": {
                                                                "facility_id": "F22S1R06",
                                                            },
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}



MGMT_SERVERS = {
    # Name, Description, Type
    ("8.8.8.8", "Google-8.8.8.8", "Name"),
    ("8.8.4.4", "Google-8.8.4.4", "Name"),
    ("1.1.1.1", "Cloudflare-1.1.1.1", "Name"),
    ("time1.google.com", "Google time1", "NTP"),
    ("time.cloudflare.com", "Cloudflare time", "NTP"),
}

# We filter locations to include only those of type 'site'
site_locations = []
for continent_name, continent_data in LOCATIONS.items():
    for country_name, country_data in continent_data["countries"].items():
        for region_name, region_data in country_data.get("regions", {}).items():
            for metro_name, metro_data in region_data.get("metros", {}).items():
                for building_name, building_data in metro_data.get("buildings", {}).items():
                    site_locations.append({"name": building_name, "shortname": building_data["shortname"]})

# We assigned a /16 per Location for "data" (257 Site possibles)
INTERNAL_POOL = IPv4Network("10.0.0.0/8").subnets(new_prefix=16)
LOCATION_SUPERNETS = {location["shortname"]: next(INTERNAL_POOL) for location in site_locations}

# We assigned a /24 per Location for "management" (257 Site possibles) <- Out of Band Access (out of /16)
MANAGEMENT_POOL = IPv4Network("172.16.0.0/16").subnets(new_prefix=24)
LOCATION_MGMTS = {location["shortname"]: next(MANAGEMENT_POOL) for location in site_locations}

# Using RFC5735 TEST-NETs as external networks
EXTERNAL_NETWORKS = [
    IPv4Network("203.0.113.0/24"),
    IPv4Network("192.0.2.0/24"),
    IPv4Network("198.51.100.0/24")
]
# We assigned one /28 per Location (48 Sites possibles)
NETWORKS_POOL_EXTERNAL = [subnet for network in EXTERNAL_NETWORKS for subnet in network.subnets(new_prefix=28)]
NETWORKS_POOL_ITER = iter(NETWORKS_POOL_EXTERNAL)
LOCATION_EXTERNAL_NETS = {location["shortname"]: next(NETWORKS_POOL_ITER) for location in site_locations}

VLANS = {
    ("100", "server-pxe"),
    ("4000", "management-ooba"),
}

# Mapping Dropdown Role and Status here
ACTIVE_STATUS = "active"

store = NodeStore()

async def create_location_hierarchy(client: InfrahubClient, log: logging.Logger, branch: str):
    orga_duff_obj = store.get(key="Duff", kind="OrganizationTenant")
    orga_eqx_obj = store.get(key="Equinix", kind="OrganizationProvider")
    orga_itx_obj = store.get(key="Interxion", kind="OrganizationProvider")
    account_crm = store.get(key="CRM Synchronization", kind="CoreAccount")

    batch_racks = await client.create_batch()

    for continent_name, continent_data in LOCATIONS.items():
        continent_shortname = continent_data["shortname"]
        continent_timezone = continent_data.get("timezone", None)
        data={
            "name": {"value": continent_name, "is_protected": True, "source": account_crm.id},
            "description": {"value": f"Continent {continent_name.lower()}"},
            "shortname": continent_shortname,
            "timezone": continent_timezone,
        }
        continent_obj = await create_and_save(
            client=client,
            log=log,
            branch=branch,
            object_name=continent_name,
            kind_name="LocationContinent",
            data=data,
            store=store,
            retrieved_on_failure=True
            )

        for country_name, country_data in continent_data["countries"].items():
            country_shortname = country_data["shortname"]
            country_timezone = country_data.get("timezone", None)
            data={
                "name": {"value": country_name, "is_protected": True, "source": account_crm.id},
                "description": {"value": f"Country {country_name.lower()}"},
                "shortname": country_shortname,
                "parent": continent_obj,
                "timezone": country_timezone,
            }
            country_obj = await create_and_save(
                client=client,
                log=log,
                branch=branch,
                object_name=country_name,
                kind_name="LocationCountry",
                data=data,
                store=store,
                retrieved_on_failure=True
                )

            for region_name, region_data in country_data.get("regions", {}).items():
                region_shortname = region_data["shortname"]
                region_timezone = region_data.get("timezone", None)
                data={
                    "name": {"value": region_name, "is_protected": True, "source": account_crm.id},
                    "description": {"value": f"Region {region_name.lower()}"},
                    "shortname": region_shortname,
                    "parent": country_obj,
                    "timezone": region_timezone,
                }
                region_obj = await create_and_save(
                    client=client,
                    log=log,
                    branch=branch,
                    object_name=region_name,
                    kind_name="LocationRegion",
                    data=data,
                    store=store,
                    retrieved_on_failure=True
                )
                name_servers = [server[0] for server in MGMT_SERVERS if server[2] == "Name"]
                random_name_server = random.choice(name_servers)

                ntp_servers = [server[0] for server in MGMT_SERVERS if server[2] == "NTP"]
                random_ntp_server = random.choice(ntp_servers)

                time_server_obj = store.get(key=random_ntp_server, kind="NetworkNTPServer")
                name_server_obj = store.get(key=random_name_server, kind="NetworkNameServer")

                mgmt_servers_obj = [name_server_obj, time_server_obj]
                mgmt_servers_obj_ids = [mgmt_server_obj.id for mgmt_server_obj in mgmt_servers_obj]
                await region_obj.add_relationships(
                    relation_to_update="network_management_servers",
                    related_nodes=mgmt_servers_obj_ids
                )

                for mgmt_server_obj in mgmt_servers_obj:
                    log.info(f"- Added {mgmt_server_obj.name.value} to {region_name}")

                for metro_name, metro_data in region_data.get("metros", {}).items():
                    metro_shortname = metro_data["shortname"]
                    data={
                        "name": {"value": metro_name, "is_protected": True, "source": account_crm.id},
                        "description": {"value": f"Metro area {metro_name.lower()}"},
                        "shortname": metro_shortname,
                        "parent": region_obj,
                     }
                    metro_obj = await create_and_save(
                        client=client,
                        log=log,
                        branch=branch,
                        object_name=metro_name,
                        kind_name="LocationMetro",
                        data=data,
                        store=store,
                        retrieved_on_failure=True
                    )

                    for building_name, building_data in metro_data.get("buildings", {}).items():
                        building_shortname = building_data["shortname"]
                        building_facility_id = building_data["facility_id"]
                        building_owner = building_data.get("owner")
                        owner_id = None
                        if building_owner == "Equinix":
                            owner_id = orga_eqx_obj.id
                        elif building_owner == "Interxion":
                            owner_id = orga_itx_obj.id
                        data={
                            "name": {"value": building_name, "is_protected": True, "source": account_crm.id},
                            "description": {"value": f"Building {building_name.lower()}"},
                            "shortname": building_shortname,
                            "facility_id": building_facility_id,
                            "owner": owner_id,
                            "parent": metro_obj,
                        }
                        building_obj = await create_and_save(
                            client=client,
                            log=log,
                            branch=branch,
                            object_name=building_name,
                            kind_name="LocationBuilding",
                            data=data,
                            store=store,
                            retrieved_on_failure=True
                        )

                        for floor_name, floor_data in building_data.get("floors", {}).items():
                            floor_shortname = floor_data["shortname"]
                            data={
                                "name": {"value": floor_name, "is_protected": True, "source": account_crm.id},
                                "description": {"value": f"Floor {floor_name.lower()}-{building_name.lower()}"},
                                "shortname": floor_shortname,
                                "parent": building_obj,
                            }
                            floor_obj = await create_and_save(
                                client=client,
                                log=log,
                                branch=branch,
                                object_name=floor_name,
                                kind_name="LocationFloor",
                                data=data,
                                store=store,
                                retrieved_on_failure=True
                            )

                            for suite_name, suite_data in floor_data.get("suites", {}).items():
                                suite_shortname = suite_data["shortname"]
                                suite_facility_id = suite_data["facility_id"]
                                suite_owner = suite_data.get("owner")
                                owner_id = None
                                if suite_owner == "Equinix":
                                    owner_id = orga_eqx_obj.id
                                elif suite_owner == "Interxion":
                                    owner_id = orga_itx_obj.id
                                elif suite_owner == "Duff":
                                    owner_id = orga_duff_obj.id
                                data={
                                    "name": {"value": suite_name, "is_protected": True, "source": account_crm.id},
                                    "description": {"value": f"Suite {suite_shortname.lower()}-{floor_shortname.lower()}-{building_shortname.lower()}"},
                                    "shortname": suite_shortname,
                                    "facility_id": suite_facility_id.upper(),
                                    "owner": owner_id,
                                    "parent": floor_obj,
                                }
                                suite_obj = await create_and_save(
                                    client=client,
                                    log=log,
                                    branch=branch,
                                    object_name=suite_name,
                                    kind_name="LocationSuite",
                                    data=data,
                                    store=store,
                                    retrieved_on_failure=True
                                )

                                for rack_name, rack_data in suite_data.get("racks", {}).items():
                                    rack_facility_id = rack_data["facility_id"]
                                    rack_owner = rack_data.get("owner")
                                    owner_id = None
                                    if rack_owner == "Duff":
                                        owner_id = orga_duff_obj.id
                                    data={
                                        "name": {"value": rack_name, "is_protected": True, "source": account_crm.id},
                                        "description": {"value": f"Rack {rack_name.lower()} in {suite_shortname.lower()}-{floor_shortname.lower()}-{building_shortname.lower()}"},
                                        "shortname": rack_name.upper(),
                                        "facility_id": rack_facility_id.upper(),
                                        "owner": owner_id,
                                        "parent": suite_obj,
                                    }
                                    rack_obj = await create_and_add_to_batch(
                                        client=client,
                                        log=log,
                                        branch=branch,
                                        object_name=rack_name,
                                        kind_name="LocationRack",
                                        data=data,
                                        store=store,
                                        batch=batch_racks,
                                    )

    async for node, _ in batch_racks.execute():
        accessor = f"{node._schema.default_filter.split('__')[0]}"
        log.info(f"- Created {node._schema.kind} - {getattr(node, accessor).value}")

async def create_location(client: InfrahubClient, log: logging.Logger, branch: str):
    # --------------------------------------------------
    # Preparing some variables for the Location
    # --------------------------------------------------
    account_pop = store.get(key="pop-builder", kind="CoreAccount")
    account_eng = store.get(key="Engineering Team", kind="CoreAccount")
    account_ops = store.get(key="Operation Team", kind="CoreAccount")

    orga_duff_obj = store.get(key="Duff", kind="OrganizationTenant")

    for mgmt_server in MGMT_SERVERS:
        mgmt_server_name = mgmt_server[0]
        mgmt_server_desc = mgmt_server[1]
        mgmt_server_type = mgmt_server[2]
        mgmt_server_kind = f"Network{mgmt_server_type}Server"
        # --------------------------------------------------
        # Create Mgmt Servers
        # --------------------------------------------------
        data={
            "name": {"value": mgmt_server_name, "is_protected": True, "source": account_eng.id},
            "description": {"value": mgmt_server_desc, "is_protected": True, "source": account_eng.id},
            "status": {"value": ACTIVE_STATUS, "is_protected": True, "source": account_eng.id},
        }
        await create_and_save(
            client=client,
            log=log,
            branch=branch,
            object_name=mgmt_server_name,
            kind_name=mgmt_server_kind,
            data=data,
            store=store,
            retrieved_on_failure=True
            )

    await create_location_hierarchy(client=client, branch=branch, log=log)

    for location in site_locations:
        location_name = location["name"]
        location_shortname = location["shortname"]

        # We cut the prefixes attributed to the Location
        location_supernet = LOCATION_SUPERNETS[location_shortname]
        location_loopback_pool = list(location_supernet.subnets(new_prefix=24))[-1]
        location_p2p_pool = list(location_supernet.subnets(new_prefix=24))[-2]
        location_vtep_pool = list(location_supernet.subnets(new_prefix=24))[-3]

        location_mgmt_pool = LOCATION_MGMTS[location_shortname]
        # mgmt_address_pool = location_mgmt.hosts()

        location_external_net = LOCATION_EXTERNAL_NETS[location_shortname]
        location_prefixes = [
            location_external_net,
            location_loopback_pool,
            location_p2p_pool,
            location_vtep_pool,
            location_mgmt_pool
            ]
        # --------------------------------------------------
        # Create VLANs
        # --------------------------------------------------
        location_obj = store.get(key=location_name, kind="LocationBuilding")
        batch = await client.create_batch()
        location_id = location_obj.id
        for vlan in VLANS:
            role = vlan[1].split("-")[0]
            vlan_name = f"{location_shortname.lower()}_{vlan[1]}"

            data={
                "name": {"value": vlan_name, "is_protected": True, "source": account_pop.id},
                "vlan_id": {"value": int(vlan[0]), "is_protected": True, "owner": account_eng.id, "source": account_pop.id},
                "description": {"value": f"{location_name.upper()} - {vlan[1].lower()} VLAN" },
                "status": {"value": ACTIVE_STATUS, "owner": account_ops.id},
                "role": {"value": role, "source": account_pop.id, "is_protected": True, "owner": account_eng.id},
                "location": {"id": location_id},
            }
            await create_and_add_to_batch(
                client=client,
                log=log,
                branch=branch,
                object_name=vlan_name,
                kind_name="InfraVLAN",
                data=data,
                store=store,
                batch=batch
                )
        async for node, _ in batch.execute():
            accessor = f"{node._schema.default_filter.split('__')[0]}"
            log.info(f"- Created {node._schema.kind} - {getattr(node, accessor).value}")

        # --------------------------------------------------
        # Create Prefix
        # --------------------------------------------------
        # TODO Add a relation between the supernets and the smaller prefixes
        batch = await client.create_batch()
        # Create Supernet
        supernet_description = f"{location_shortname.lower()}-supernet-{IPv4Network(location_supernet).network_address}"
        data = {
            "prefix":  {"value": location_supernet },
            "description": {"value": supernet_description},
            "organization": {"id": orga_duff_obj.id },
            "location": {"id": location_id },
            "status": {"value": "active" },
            "role": {"value": "supernet" },
        }
        supernet_obj = await create_and_save(
            client=client,
            log=log,
            branch=branch,
            object_name=location_supernet,
            kind_name="InfraPrefix",
            data=data,
            store=store
        )
        # Create /24 specifics subnets Pool
        for prefix in location_prefixes:
            # vlan_id = None
            if any(prefix.subnet_of(external_net) for external_net in EXTERNAL_NETWORKS):
                prefix_status = "active"
                prefix_description = f"{location_shortname.lower()}-ext-{IPv4Network(prefix).network_address}"
                prefix_role = "public"
                vrf_id = store.get(key="Internet", kind="InfraVRF").id
            elif prefix.subnet_of(location_mgmt_pool):
                prefix_status = "active"
                prefix_description = f"{location_shortname.lower()}-mgmt-{IPv4Network(prefix).network_address}"
                prefix_role = "management"
                vrf_id = store.get(key="Management", kind="InfraVRF").id
            else:
                prefix_status = "reserved"
                prefix_role = "technical"
                vrf_id = store.get(key="Backbone", kind="InfraVRF").id
                if  prefix.subnet_of(location_p2p_pool):
                    prefix_description = f"{location_shortname.lower()}-p2p-{IPv4Network(prefix).network_address}"
                elif  prefix.subnet_of(location_vtep_pool):
                    prefix_description = f"{location_shortname.lower()}-vtep-{IPv4Network(prefix).network_address}"
                    prefix_role = "loopback-vtep"
                if  prefix.subnet_of(location_loopback_pool):
                    prefix_description = f"{location_shortname.lower()}-loop-{IPv4Network(prefix).network_address}"
                    prefix_role = "loopback"
            data = {
                "prefix":  {"value": prefix },
                "description": {"value": prefix_description},
                "organization": {"id": orga_duff_obj.id },
                "location": {"id": location_id },
                "status": {"value": prefix_status },
                "role": {"value": prefix_role },
                "ip_namespace": { "id": vrf_id },
            }

            prefix_obj = await create_and_save(
                client=client,
                log=log,
                branch=branch,
                object_name=prefix,
                kind_name="InfraPrefix",
                data=data,
                store=store,
                batch=batch
                )
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

    # ------------------------------------------
    # Create Sites
    # ------------------------------------------
    log.info("Retrieving objects from Infrahub")
    try:
        accounts=await client.all("CoreAccount")
        populate_local_store(objects=accounts, key_type="name", store=store)
        tenants=await client.all("OrganizationTenant")
        populate_local_store(objects=tenants, key_type="name", store=store)
        providers=await client.all("OrganizationProvider")
        populate_local_store(objects=providers, key_type="name", store=store)
        autonomous_systems=await client.all("InfraAutonomousSystem")
        populate_local_store(objects=autonomous_systems, key_type="name", store=store)
        groups=await client.all("CoreStandardGroup")
        populate_local_store(objects=groups, key_type="name", store=store)
        vrfs=await client.all("InfraVRF")
        populate_local_store(objects=vrfs, key_type="name", store=store)

    except Exception as e:
        log.info(f"Fail to populate due to {e}")
        exit(1)

    log.info("Generation Location")
    await create_location(client=client, branch=branch, log=log)
