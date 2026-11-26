"""Pure counting transitions and a MongoDB compare-and-swap store."""
from copy import deepcopy

MAX_COUNT=10**12


def initial(guild_id,channel_id):
    return {'_id':f'{guild_id}:{channel_id}','guild_id':guild_id,'channel_id':channel_id,
            'version':0,'count':0,'record':0,'last_user':None,'last_message':0,
            'participants':[],'started_at':None,'record_at_start':0,'announced_record':False,
            'last_ended':None,'restores':[]}


def apply_count(state,number,user_id,message_id,now):
    if message_id<=state['last_message']:
        return 'duplicate',state,{}
    new=deepcopy(state)
    new['last_message']=message_id
    expected=state['count']+1
    if number!=expected or state['last_user']==user_id:
        reason='same_user' if number==expected else 'wrong_number'
        stats={'count':state['count'],'record':state['record'],'participants':len(state['participants']),
               'duration':max(0,int(now-state['started_at'])) if state['started_at'] is not None else 0,
               'expected':expected,'received':number,'reason':reason}
        if state['count']>0:
            new['last_ended']={k:deepcopy(state[k]) for k in ('count','last_user','participants','started_at','record_at_start','announced_record')}
        new.update(count=0,last_user=None,participants=[],started_at=None,record_at_start=state['record'],announced_record=False)
        return 'reset',new,stats
    if state['count']==0:
        new.update(started_at=now,record_at_start=state['record'],announced_record=False)
    new['count']=number
    new['last_user']=user_id
    if user_id not in new['participants']:
        new['participants'].append(user_id)
    new['record']=max(state['record'],number)
    record=new['record_at_start']>0 and number>new['record_at_start'] and not new['announced_record']
    if record: new['announced_record']=True
    return 'accepted',new,{'record':record}


def apply_restore(state,number,moderator,reason,now):
    if not 0<=number<=state['record'] or number>MAX_COUNT:
        raise ValueError('Restore must be between 0 and the existing all-time record.')
    if not reason.strip() or len(reason)>300:
        raise ValueError('Provide a reason of 1–300 characters.')
    new=deepcopy(state)
    snapshot=state.get('last_ended')
    if number==state['count']:
        raise ValueError('The count is already at that number.')
    if number>0 and snapshot and snapshot['count']==number:
        new.update(deepcopy(snapshot))
    else:
        new.update(count=number,last_user=None,participants=[],started_at=now if number else None,
                   record_at_start=state['record'],announced_record=False)
    new['restores']=(state.get('restores',[])+[{'moderator':moderator,'from':state['count'],'to':number,'reason':reason,'at':now}])[-100:]
    return new


class CountingStore:
    def __init__(self,database):
        self.collection=database['counting']

    async def read(self,guild_id,channel_id):
        from pymongo.errors import DuplicateKeyError
        default=initial(guild_id,channel_id)
        try:
            await self.collection.update_one({'_id':default['_id']},{'$setOnInsert':default},upsert=True)
        except DuplicateKeyError:
            pass
        state=await self.collection.find_one({'_id':default['_id']})
        if state is None: raise RuntimeError('Counting state unavailable.')
        return state

    async def commit(self,old,new):
        new=deepcopy(new); new['version']=old['version']+1
        result=await self.collection.replace_one({'_id':old['_id'],'version':old['version']},new)
        return result.modified_count==1
