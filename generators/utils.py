import logging

from typing import Dict, List, Optional

from infrahub_sdk import InfrahubClient, InfrahubNode, NodeStore
from infrahub_sdk.batch import InfrahubBatch
from infrahub_sdk.exceptions import GraphQLError

async def create_and_save(
        client: InfrahubClient,
        log: logging.Logger,
        branch: str,
        object_name: str,
        kind_name: str,
        data: Dict,
        store: NodeStore,
        allow_upsert: Optional[bool] = True,
        retrieved_on_failure: Optional[bool] = False,
    ) -> InfrahubNode:
    """Creates an object, saves it and handles failures."""
    try:
        obj = await client.create(branch=branch, kind=kind_name, data=data)
        await obj.save(allow_upsert=allow_upsert)
        log.info(f"- Created {obj._schema.kind} - {object_name}")
        store.set(key=object_name, node=obj)
    except GraphQLError as exc:
        log.debug(f"- Creation failed for {obj._schema.kind} - {object_name} due to {exc}")
        if retrieved_on_failure:
            obj = await client.get(kind=kind_name, name__value=object_name)
            store.set(key=object_name, node=obj)
            log.info(f"- Retrieved {obj._schema.kind} - {object_name}")
    return obj

async def create_and_add_to_batch(
        client: InfrahubClient,
        log: logging.Logger,
        branch: str,
        object_name: str,
        kind_name: str,
        data: Dict,
        batch: InfrahubBatch,
        store: NodeStore,
        allow_upsert: Optional[bool] = True,
    ) -> InfrahubNode:
    """Creates an object and adds it to a batch for deferred saving."""
    obj = await client.create(branch=branch, kind=kind_name, data=data)
    batch.add(task=obj.save, allow_upsert=allow_upsert, node=obj)
    log.debug(f"- Added to batch: {obj._schema.kind} - {object_name}")
    store.set(key=object_name, node=obj)
    return obj

def populate_local_store(objects: List[InfrahubNode], key_type: str, store: NodeStore):

    for obj in objects:
        key = getattr(obj, key_type)
        if key:
            store.set(key=key.value, node=obj)
