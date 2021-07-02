import os
import sys
import json
import unittest

#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from one_to_one import looper


class TestBasics(unittest.TestCase):

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
                    #"source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "item": {
                        "type": "string",
                        "example": "interval 10",

                    }
                }
            }
        }

        result = looper(input_data)
        self.assertDictEqual(result, expected)

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
                        #"source": {"type": "index", "index": 0},
                    },
                    {
                        #"title": "counter",
                        "type": "float",
                        "example": "5164.23076923",
                        #"type": "string",
                        #"field_type": "float",
                        #"source": {"type": "index", "index": 1},

                    }                                                                                      
                ]
            }
        }


        result = looper(input_data)
        self.assertDictEqual(result, expected)

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
                            "item": {
                                "type": "dict",
                                "nested": {
                                    "ip_name": {
                                        "title": "Ip Name",
                                        "example": "172.0.0.1",
                                        "type": "string"
                                    },
                                    "vlan": {
                                        "title": "Vlan",
                                        "example": "my_vlan",
                                        "type": "string"
                                    },
                                    "ip_address": {
                                        "title": "Ip Address",
                                        "example": "172.0.0.1",
                                        "type": "string"
                                    },
                                    "mac_address": {
                                        "title": "Mac Address",
                                        "example": "00:00:00:00:00:00",
                                        "type": "string"
                                    },
                                    "interface_name": {
                                        "title": "Interface Name",
                                        "example": "backend_name1",
                                        "type": "string"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }



        result = looper(input_data)
        print(json.dumps(result, indent=4))
        self.assertDictEqual(result, expected)

        

if __name__ == "__main__":
    unittest.main()
