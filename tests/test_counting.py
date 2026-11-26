import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from utils.counting_store import initial,apply_count,apply_restore

def play(state,n,user,mid,t=100):
    action,new,stats=apply_count(state,n,user,mid,t)
    return action,new,stats

def test_streak_reset_restore():
    s=initial(1,2)
    a,s,_=play(s,1,10,100); assert a=='accepted'
    a,s,_=play(s,2,20,101,110); assert a=='accepted'
    a,s,_=play(s,3,10,102,120); assert a=='accepted'
    a,s,stats=play(s,5,20,103,130)
    assert a=='reset' and s['count']==0 and s['record']==3
    assert stats['participants']==2 and stats['duration']==30
    s=apply_restore(s,3,99,'Test restore',140)
    assert s['count']==3 and s['record']==3 and s['last_user']==10
    a,s,_=play(s,4,20,104,150); assert a=='accepted'
    assert s['record']==4 and s['restores'][0]['moderator']==99

def test_consecutive():
    _,s,_=play(initial(1,2),1,10,100)
    a,s,stats=play(s,2,10,101)
    assert a=='reset' and stats['reason']=='same_user'

def test_duplicate_and_out_of_order():
    _,s,_=play(initial(1,2),1,10,100)
    assert play(s,2,20,100)[0]=='duplicate'
    assert play(s,2,20,99)[0]=='duplicate'
    assert s['count']==1

def test_record_announcement_once():
    _,s,_=play(initial(1,2),1,10,100)
    _,s,_=play(s,9,20,101)
    _,s,d=play(s,1,10,102); assert not d['record']
    _,s,d=play(s,2,20,103); assert d['record']
    _,s,d=play(s,3,10,104); assert not d['record']

def test_invalid_restore():
    s=initial(1,2)
    with pytest.raises(ValueError): apply_restore(s,1,99,'reason',100)
    with pytest.raises(ValueError): apply_restore(s,0,99,'',100)

def test_no_mutation_before_commit():
    s=initial(1,2)
    _,new,_=play(s,1,10,100)
    assert s['count']==0 and new['count']==1
    assert s['participants']==[]

def test_zero_restore_preserves_record():
    _,s,_=play(initial(1,2),1,10,100)
    r=apply_restore(s,0,99,'reset',101)
    assert r['record']==1 and r['count']==0
