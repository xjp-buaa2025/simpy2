"""Hosting leases are independent of publishers, viewers and the simulation clock."""
import pytest
from fastapi import HTTPException
from app.api.vr_mirror import HostLeases


def test_host_release_multiple_clients_and_expiry():
    now=[100.0]
    hosts=HostLeases(lambda:now[0])
    assert hosts.count()==0 and not hosts.ever_registered
    assert hosts.update('pc_a',True)==1
    assert hosts.update('pc_b',True)==2
    assert hosts.update('pc_a',False)==1
    now[0]+=11
    assert hosts.count()==1
    hosts.update('pc_b',True)
    now[0]+=13
    assert hosts.count()==0 and hosts.ever_registered


def test_invalid_host_does_not_acquire_a_lease():
    hosts=HostLeases()
    with pytest.raises(HTTPException):hosts.update('../bad',True)
    assert hosts.count()==0 and not hosts.ever_registered
