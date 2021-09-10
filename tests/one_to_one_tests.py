import os
import sys
import json
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from one_to_one import one_to_one_looper, CONFIG

from semantic_model import run_detail, run_list, InvalidModel, get_by_dn, yield_by_dn
from semantic_model import run_nodes, iter_by_key


def create_dn(dn, title, index=None):
    if dn == "":
        return title

    if index != None:
        return f"{dn}.[{index}]"

    return f"{dn}.{title}"


def differ(a, b):
    try:
        diff(a, b)
    except Exception as e:
        return e.args[0]

def diff(a, b, dn=""):
    if type(a) != type(b):
        return False, dn
    elif isinstance(a, dict):
        for k, v in a.items():
            dn_ = create_dn(dn, k)
            try:
                diff(v, b[k], dn=dn_)
            except KeyError as e:
                raise Exception(f"missing key, on dn: {dn_}")
            except TypeError as e:
                raise Exception(f"missing key, on dn: {e}")
    elif isinstance(a, list):
        for i, v in enumerate(a):
            dn_ = create_dn(dn, None, i)
            try:
                diff(v, b[i], dn=dn_)
            except IndexError:
                raise Exception(f"missing index on dn {dn_}")
    elif a != b:
        raise Exception(f"not equal: {a} != {b} on {dn}")
    else:
        return "Fallthrough"


def test_output(result, expected):
    return f"\nresult:\n{json.dumps(result, indent=4)}\nexpected:\n{json.dumps(expected, indent=4)}\n\n{differ(result, expected)}"


class TestBasics(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        CONFIG["skip_description"] = True
        CONFIG["skip_source"] = True

    @classmethod
    def tearDownClass(cls):
        del CONFIG["skip_description"]
        del CONFIG["skip_source"]

    def test_basics(self):
        input_data = {
            "options": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }
        expected = {
            "type": "dict",
            "nested": {
                "options": { 
                    "title": "Options",
                    "type": "list",
                    #"source": {"type": "dn_lookup_loop", "source": "input", "dn": "items", "multi": True},
                    "item": {
                        "example": "interval 10",
                        "description": "",
                        "type": "string",


                    }
                }
            }
        }

        result = one_to_one_looper(input_data)
        self.assertDictEqual(result, expected, test_output(result, expected))

    def test_basics_nested(self):
        input_data = {
           "domain": {
                "arp": [
                    {
                        "ip_name": "172.0.0.1",
                        "vlan": "my_vlan",
                        "ip_address": "172.0.0.1",
                        "mac_address": "00:00:00:00:00:00",
                        "interface_name": "backend_name1",
                    },
                    {
                        "ip_name": "127.0.0.1",
                        "vlan": "other_vlan",
                        "ip_address": "127.0.0.1",
                        "mac_address": "01:01:01:01:01:01",
                        "interface_name": "mgmt_name2",
                    }
                ]
           }
        }


        expected = {
            "type": "dict",
            "nested": {
                "domain": {
                    "title": "Domain",
                    "type": "dict",
                    "nested": {
                        "arp": {
                            "title": "Arp",
                            "type": "list",
                            "nested": {
                                "ip_name": {
                                    "title": "Ip Name",
                                    "type": "string",
                                    "field_type": "ipv4",
                                    "example": "172.0.0.1",
                                    "description": ""
                                },
                                "vlan": {
                                    "title": "Vlan",
                                    "type": "string",
                                    "example": "my_vlan",
                                    "description": ""
                                },
                                "ip_address": {
                                    "title": "Ip Address",
                                    "type": "string",
                                    "field_type": "ipv4",
                                    "example": "172.0.0.1",
                                    "description": ""
                                },
                                "mac_address": {
                                    "title": "Mac Address",
                                    "type": "string",
                                    "example": "00:00:00:00:00:00",
                                    "description": ""
                                },
                                "interface_name": {
                                    "title": "Interface Name",
                                    "type": "string",
                                    "example": "backend_name1",
                                    "description": ""
                                }
                            }
                        }
                    }
                }
            }
        }

        result = one_to_one_looper(input_data)
        self.assertDictEqual(result, expected, test_output(result, expected))


class Testgather(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CONFIG["skip_description"] = True

    @classmethod
    def tearDownClass(cls):
        del CONFIG["skip_description"]

    def test_basic_gather_sm_works(self):
        input_data = {
            "options": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }
        expected = {
            "type": "dict",
            "nested": {
                "options": { 
                    "title": "Options",
                    "type": "list",
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "options"},
                    "item": {
                        "source": {"type": "yield"},
                        "type": "string",
                        "example": "interval 10",
                        "description": "",
                    }
                }
            }
        }

        dsm_model = one_to_one_looper(input_data)
        self.assertDictEqual(dsm_model, expected, test_output(dsm_model, expected))
        result = run_detail(dsm_model, input=input_data)
        self.assertDictEqual(result, input_data, test_output(result, input_data))

    def test_basics_nested_gather(self):
        input_data = {
           "domain": {
                "arp": [
                    {
                        "ip_name": "172.0.0.1",
                        "vlan": "my_vlan",
                        "ip_address": "172.0.1.1",
                        "mac_address": "00:00:00:00:00:00",
                        "interface_name": "backend_name1",
                    },
                    {
                        "ip_name": "127.0.0.1",
                        "vlan": "other_vlan",
                        "ip_address": "127.0.1.1",
                        "mac_address": "01:01:01:01:01:01",
                        "interface_name": "mgmt_name2",
                    }
                ]
           }
        }
        expected = {
            "type": "dict",
            "nested": {
                "domain": {
                    "title": "Domain",
                    "type": "dict",
                    "source": {}, 
                    "nested": {
                        "arp": {
                            "title": "Arp",
                            "type": "list",
                            "source": {"type": "dn_lookup_loop", "source": "input", "dn": "domain.arp"},
                            "nested": {
                                "ip_name": {
                                    "title": "Ip Name",
                                    "type": "string",
                                    "source": {"type": "json_key_item", "dn": "ip_name"},
                                    "field_type": "ipv4",
                                    "example": "172.0.0.1",
                                    "description": ""
                                },
                                "vlan": {
                                    "title": "Vlan",
                                    "type": "string",
                                    "source": {"type": "json_key_item", "dn": "vlan"}, 
                                    "example": "my_vlan",
                                    "description": ""
                                },
                                "ip_address": {
                                    "title": "Ip Address",
                                    "type": "string",
                                    "source": {"type": "json_key_item", "dn": "ip_address"}, 
                                    "field_type": "ipv4",
                                    "example": "172.0.1.1",
                                    "description": ""
                                },
                                "mac_address": {
                                    "title": "Mac Address",
                                    "type": "string",
                                    "source": {"type": "json_key_item", "dn": "mac_address"}, 
                                    "example": "00:00:00:00:00:00",
                                    "description": ""
                                },
                                "interface_name": {
                                    "title": "Interface Name",
                                    "type": "string",
                                    "source": {"type": "json_key_item", "dn": "interface_name"}, 
                                    "example": "backend_name1",
                                    "description": ""
                                }
                            }
                        }
                    }
                }
            }
        }

        dsm_model = one_to_one_looper(input_data)
        self.assertDictEqual(dsm_model, expected, test_output(dsm_model, expected))
        result = run_detail(dsm_model, input=input_data)
        #result = run_detail(expected, input=input_data)
        
        self.assertDictEqual(result, input_data, test_output(result, input_data))


@unittest.skip("Should be added, but for now dictonary is always top level")
class TestgatherList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CONFIG["skip_description"] = True

    @classmethod
    def tearDownClass(cls):
        del CONFIG["skip_description"]

    @unittest.skip("Should be added, but for now dictonary is always top level")
    def test_basics_list_double_type(self):
        input_data= [
            [
                "2020-03-26T15:00:00Z",
                5164.23076923
            ],
            [
                "2020-03-26T15:00:01Z",
                5164.23076924
            ]
        ]
        expected = {
            "type": "list",
            #"source": {"type": "loop_over", "source": "input", "dn": ""},
            "item": {
                "type": "list",
                "items": [
                    {
                        #"title": "timestamp",
                        "type": "string", 
                        "example": "2020-03-26T15:00:00Z",
                        "description": "",
                        #"source": {"type": "index", "index": 0},
                    },
                    {
                        #"title": "counter",
                        "type": "float",
                        "example": "5164.23076923",
                        "description": "",
                        #"source": {"type": "index", "index": 1},

                    }                                                                                      


                ]
            }
        }


        result = one_to_one_looper(input_data)
        self.assertDictEqual(result, expected, test_output(result, expected))

    @unittest.skip("Should be added, but for now dictonary is always top level")
    def test_basic_gather_sm_works(self):
        input_data = {
            "options": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }
        expected = {
            "type": "dict",
            "nested": {
                "options": { 
                    "title": "Options",
                    "type": "list",
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "options"},
                    "item": {
                        "source": {"type": "yield"},
                        "type": "string",
                        "example": "interval 10",
                        "description": "",
                    }
                }
            }
        }

        print('-------------****------------')

        dsm_model = one_to_one_looper(input_data)
        self.assertDictEqual(dsm_model, expected, test_output(dsm_model, expected))
        result = run_detail(dsm_model, input=input_data)
        self.assertDictEqual(result, input_data, test_output(result, input_data))
    
    @unittest.skip("Should be added, but for now dictonary is always top level")
    def test_basics_list_double_type_gather(self):
        input_data= [
            [
                "2020-03-26T15:00:00Z",
                5164.23076923
            ],
            [
                "2020-03-26T15:00:01Z",
                5164.23076924
            ]
        ]
        expected = {
            "type": "list",
            "item": {
                "type": "list",
                "source": {"type": "dn_lookup_loop", "source": "input", "dn": "[]"},
                "items": [
                    {
                        "type": "string",
                        "source": {
                            "type": "yield",
                            "index": "0"
                        },
                        "example": "2020-03-26T15:00:00Z",
                        "description": ""
                    },
                    {
                        "type": "float",
                        "source": {
                            "type": "yield",
                            "index": "1"
                        },
                        "example": "5164.23076923",
                        "description": ""
                    }
                ]
            }
        }



        dsm_model = one_to_one_looper(input_data)
        self.assertDictEqual(dsm_model, expected, test_output(dsm_model, expected))
        dic_result = {"result": run_detail(dsm_model, input=input_data)}
        dic_input_data = {"result": input_data}
        

        self.assertDictEqual(dic_result, dic_input_data, test_output(dic_result, dic_input_data))

if __name__ == "__main__":
    unittest.main()
