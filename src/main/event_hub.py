import asyncio
from typing import Any
import weakref

class EventHub:

    def __init__(self):
        self._event_type_to_refid_to_coroutine_wref_dict_dict:dict[str,dict[int,Any]] = {}
        self._next_refid:int = 1

    def subscribe(self, event_type: str, coroutine) -> int:
        if event_type not in self._event_type_to_refid_to_coroutine_wref_dict_dict:
            self._event_type_to_refid_to_coroutine_wref_dict_dict[event_type] = {}
        refid_to_coroutine_wref_dict = self._event_type_to_refid_to_coroutine_wref_dict_dict[event_type]
        refid = self._next_refid
        refid_to_coroutine_wref_dict[refid] = weakref.WeakMethod(coroutine)
        self._next_refid += 1
        return refid

    def unsubscribe(self, event_type: str, refid: int):
        if event_type not in self._event_type_to_refid_to_coroutine_wref_dict_dict:
            return
        refid_to_coroutine_wref_dict = self._event_type_to_refid_to_coroutine_wref_dict_dict[event_type]
        if refid not in refid_to_coroutine_wref_dict:
            return
        del refid_to_coroutine_wref_dict[refid]

    async def publish_async(self, event_type, *args, **kwargs):
        if event_type not in self._event_type_to_refid_to_coroutine_wref_dict_dict:
            return
        refid_to_coroutine_wref_dict = self._event_type_to_refid_to_coroutine_wref_dict_dict[event_type]
        dead_refid_list = []
        async with asyncio.TaskGroup() as tg:
            for refid, coroutine_wref in refid_to_coroutine_wref_dict.items():
                coroutine = coroutine_wref()
                if coroutine is not None:
                    tg.create_task(coroutine(event_type, *args, **kwargs))
                else:
                    dead_refid_list.append(refid)
        for refid in dead_refid_list:
            del refid_to_coroutine_wref_dict[refid]
