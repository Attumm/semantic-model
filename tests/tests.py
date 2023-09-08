import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from semantic_model import run_detail, run_list, InvalidModel, get_by_dn, yield_by_dn
from semantic_model import run_nodes, iter_by_key


class TestBasics(unittest.TestCase):

    def test_basics(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        expected = {
            "options": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        dsm_model = {
            "type": "dict",
            "nested": {
                "options": {
                    "type": "list",
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "item": {
                        "type": "string",
                    }
                }
            }
        }
        result = run_detail(dsm_model, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_timeseries(self):

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

        expected = [
            [
                "2020-03-26T15:00:00Z",
                5164.23076923
            ],
            [
                "2020-03-26T15:00:01Z",
                5164.23076924
            ]
        ]

        dsm_model = {
            "type": "list",
            "source": {"type": "loop_over", "source": "input", "dn": ""},
            "item": {
                "type": "list",
                "items": [
                    {
                        "title": "timestamp",
                        "type": "string",
                        "source": {"type": "index", "index": 0},
                    },
                    {
                        "title": "counter",
                        "type": "string",
                        "field_type": "float",
                        "source": {"type": "index", "index": 1},
                    }
                ]
            }

        }
        result = run_detail(dsm_model, input=input_data)
        self.assertEqual(result, expected)

    def test_basics_rbac_restricted(self):
        input_data = {
            "items": [
                "interval 1",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there, I'm 4",
                "Thinking of another generic string five",
                "Last one boys, six"
            ]
        }

        expected = {}

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                "full": {"read": True},
                "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                    },
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "description": "options of counting items",
                    "item": {
                        "type": "string",
                        "example": "Random strings",
                    }
                }
            }
        }
        roles = ["restricted",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_rbac_full(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        expected = {
            "options": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                    "full": {"read": True},
                    "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                    },
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "description": "",
                    "item": {
                        "type": "string",
                        "rbac": {
                            "full": {"read": True},
                        },
                    }
                }
            }
        }

        roles = ["full",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_role_read_right_is_bool(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        expected = {}

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                    "full": {"read": True},
                    "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "full": {"read": "True"},  # is string not bool
                    },
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "description": "",
                    "item": {
                        "type": "string",
                    }
                }
            }
        }

        roles = ["full",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_view_right_for_key_not_items_list_items(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        expected = {
            "options": [],
        }

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                    "full": {"read": True},
                    "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                    },
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "items"},
                    "description": "",
                    "item": {
                        "type": "string",
                    }
                }
            }
        }

        roles = ["full",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_rbac_multiple_items_empty_result(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
            ]
        }

        expected = {}

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                    "full": {"read": True},
                    "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                    },  # rbac, is only for full ###
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "items"},
                    "description": "",
                    "item": {
                        "type": "string",
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                },
                "items": {
                    "title": "Items",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                    },
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "items"},
                    "description": "",
                    "item": {
                        "type": "string",
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                }
            }
        }

        roles = "restricted"
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_rbac_multiple_items_empty_no_read_rbac_result(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
            ]
        }

        expected = {}

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                    "full": {"read": True},
                    "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "full": {"update": True},
                    },  # rbac, is only for full ###
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "items"},
                    "description": "",
                    "item": {
                        "type": "string",
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                },
                "items": {
                    "title": "Items",
                    "type": "list",
                    "rbac": {
                        "full": {"update": True},
                    },
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "items"},
                    "description": "",
                    "item": {
                        "type": "string",
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                }
            }
        }

        roles = ["full", ]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_rbac_multiple_items_empty_single_result(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
            ]
        }

        expected = {
            "items": [
                "interval 10",
                "item that is in the second place",
            ],
        }

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                "full": {"read": True},
                "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                    }, # rbac, is only for full
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "items"},
                    "description": "",
                    "item": {
                        "type": "string",
                        "rbac": {
                            "full": {"read": True},
                        },
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                },
                "items": {
                    "title": "Items",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                        "restricted": {"read": True}
                    },
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "items"},
                    "description": "",
                    "item": {
                        "type": "string",
                        "rbac": {
                            "full": {"read": True},
                            "restricted": {"read": True}
                        },

                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                }
            }
        }

        roles = ["restricted", ]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_rbac_multiple_items_full(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
            ]
        }

        expected = {
            "items": [
                "interval 10",
                "item that is in the second place",
            ],
            "options": [
                "interval 10",
                "item that is in the second place",
            ]
        }

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                "full": {"read": True},
                "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                            "full": {"read": True},
                            "restricted": {"read": True}
                    },  # rbac, is only for full
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "description": "",
                    "item": {
                        "type": "string",
                        "rbac": {
                            "full": {"read": True},
                            "restricted": {"read": True}
                        },
                        "example": "",
                    }
                },
                "items": {
                    "title": "Items",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                        "restricted": {"read": True}
                    },
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "description": "",
                    "item": {
                        "type": "string",
                        "rbac": {
                            "full": {"read": True},
                            "restricted": {"read": True}
                        },
                        "example": "",
                    }
                }
            }
        }

        roles = ["full",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_rbac_nested(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
            ]
        }

        expected = {
            "items": [
                "interval 10",
                "item that is in the second place",
            ],
            "options": [
                "interval 10",
                "item that is in the second place",
            ]
        }

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                "full": {"read": True},
                "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                        "restricted": {"read": True}
                    },  # rbac, is only for full
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "description": "",
                    "item": {
                        "type": "string",
                        "rbac": {
                            "full": {"read": True},
                            "restricted": {"read": True}
                        },
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                },
                "items": {
                    "title": "Items",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                        "restricted": {"read": True}
                    },
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "description": "",
                    "item": {
                        "type": "string",
                        "rbac": {
                            "full": {"read": True},
                            "restricted": {"read": True}
                        },
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                }
            }
        }

        roles = ["full",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_rbac_nested_filter_list_item(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
            ]
        }

        expected = {
            "items": [
                "item that is in the second place",
            ],
            "options": [
                "interval 10",
            ]
        }

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                "full": {"read": True},
                "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                        "restricted": {"read": True}
                    },  # rbac, is only for full
                    "source": {
                        "type": "json_key", "source": "input", "dn": "items", "multi": True,
                        "filter_type": "not_contains", "filter_args": {"arg": "10"},
                        },
                    "description": "",
                    "item": {
                        "type": "string",
                        "rbac": {
                            "full": {"read": True},
                            "restricted": {"read": True}
                        },
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                },
                "items": {
                    "title": "Items",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                        "restricted": {"read": True}
                    },
                    "source": {
                        "type": "json_key", "source": "input", "dn": "items", "multi": True,
                        "filter_type": "contains", "filter_args": {"arg": "10"},
                    },
                    "description": "",
                    "item": {
                        "type": "string",
                        "rbac": {
                            "full": {"read": True},
                            "restricted": {"read": True}
                        },
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                }
            }
        }

        roles = ["full",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_rbac_multiple_items_full__FEFE_(self):
        input_data = {
           "Domain": {
                "ARPS": [
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
           }}

        expected = {
            "arp": [
                {
                    "name": "172.0.0.1",
                    "vlan": "my_vlan",
                    "ip_address": "172.0.0.1",
                },
                {
                    "name": "127.0.0.1",
                    "vlan": "other_vlan",
                    "ip_address": "127.0.0.1"
                }
            ]
        }
        dsm_model = {
            "title": "Name of DSM Model",
            "type": "dict",
            "description": "",
            "nested": {
                "arp": {
                    "title": "Arp",
                    "type": "list",
                    "description": "Address Resolution Protocol",
                    "source": {"type": "dn_lookup", "source": "input", "dn": "Domain.ARPS"},
                    "nested": {
                        "name": {
                            "title": "Name",
                            "type": "string",
                            "example": "62.179.85.185",
                            "source": {"type": "key_lookup",  "key": "ip_name"},
                            "description": "Name of the ARP rule",
                        },
                        "vlan": {
                            "title": "VLAN",
                            "type": "string",
                            "example": "NL_SRK03A_FE_VLB_ATUCF_-T3749.0",
                            "source": {"type": "key_lookup", "key": "vlan"},
                            "description": "",
                        },
                        "ip_address": {
                            "title": "IP Address",
                            "type": "string",
                            "field_type": "ipv4_address",
                            "example": "62.179.85.185",
                            "source": {"type": "key_lookup", "key": "ip_address"},
                            "description": ""
                        }
                    }
                }
            }
        }

        result = run_detail(dsm_model, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_rbac_multiple_items_full_remove_by_view_(self):
        input_data = {
           "Domain": {
                "ARPS": [
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
           }}

        expected = {
            "arp": [
                {
                    "name": "172.0.0.1",
                    "ip_address": "172.0.0.1",
                },
                {
                    "name": "127.0.0.1",
                    "ip_address": "127.0.0.1"
                }
            ]
        }

        dsm_model = {
            "title": "Name of DSM Model",
            "type": "dict",
            "description": "",
            "rbac": {"admin": {"read": True}},
            "nested": {
                "arp": {
                    "title": "Arp",
                    "type": "list",
                    "rbac": {"admin": {"read": True}},
                    "description": "Address Resolution Protocol",
                    "source": {"type": "dn_lookup", "source": "input", "dn": "Domain.ARPS", "multi": True},
                    "nested": {
                        "name": {
                            "title": "Name",
                            "rbac": {"admin": {"read": True}},
                            "type": "string",
                            "example": "62.179.85.185",
                            "source": {"type": "key_lookup",  "key": "ip_name"},
                            "description": "Name of the ARP rule",
                        },
                        "vlan": {
                            "title": "VLAN",
                            "type": "string",
                            "example": "NL_SRK03A_FE_VLB_ATUCF_-T3749.0",
                            "source": {"type": "key_lookup", "key": "vlan"},
                            "description": "",
                        },
                        "ip_address": {
                            "title": "IP Address",
                            "type": "string",
                            "rbac": {"admin": {"read": True}},
                            "field_type": "ipv4_address",
                            "example": "62.179.85.185",
                            "source": {"type": "key_lookup", "key": "ip_address"},
                            "description": ""
                        }
                    }
                }
            }
        }

        roles = ["admin",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_filter_type_list(self):
        input_data = {
           "Domain": {
                "ARPS": [
                    {
                        "ip_name": "172.0.0.1",
                        "vlan": "my_vlan",
                        "ip_address": "172.0.0.1",
                        "mac_address": "00:00:00:00:00:00",
                        "interface_name": "backend_name1",
                        "status": "",
                    },
                    {
                        "ip_name": "127.0.0.1",
                        "vlan": "other_vlan",
                        "ip_address": "127.0.0.1",
                        "mac_address": "01:01:01:01:01:01",
                        "interface_name": "mgmt_name2",
                        "status": "True",
                    }
                ]
           }}

        expected = {
            "arp": [
                {
                    "name": "127.0.0.1",
                    "ip_address": "127.0.0.1"
                }
            ]
        }

        dsm_model = {
            "title": "Name of DSM Model",
            "type": "dict",
            "description": "",
            "rbac": {"admin": {"read": True}},
            "nested": {
                "arp": {
                    "title": "Arp",
                    "type": "list",
                    "rbac": {"admin": {"read": True}},
                    "description": "Address Resolution Protocol",
                    "source": {
                        "type": "dn_lookup", "source": "input", "dn": "Domain.ARPS", "multi": True,
                        "filter_type": "dict_key_is_empty", "filter_args": {"key": "status"}
                    },
                    "nested": {
                        "name": {
                            "title": "Name",
                            "rbac": {"admin": {"read": True}},
                            "type": "string",
                            "example": "62.179.85.185",
                            "source": {"type": "key_lookup",  "key": "ip_name"},
                            "description": "Name of the ARP rule",
                        },
                        "vlan": {
                            "title": "VLAN",
                            "type": "string",
                            "example": "NL_SRK03A_FE_VLB_ATUCF_-T3749.0",
                            "source": {"type": "key_lookup", "key": "vlan"},
                            "description": "",
                        },
                        "ip_address": {
                            "title": "IP Address",
                            "type": "string",
                            "rbac": {"admin": {"read": True}},
                            "field_type": "ipv4_address",
                            "example": "62.179.85.185",
                            "source": {"type": "key_lookup", "key": "ip_address"},
                            "description": ""
                        }
                    }
                }
            }
        }

        roles = ["admin",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_filter_quite_nested_type_list(self):
        input_data = {
           "Domain": {
                "ARPS": [
                    {
                        "ip_name": "172.0.0.1_ip_name",
                        "vlan": "my_vlan",
                        "ip_address": "172.0.0.1",
                        "mac_address": "00:00:00:00:00:00",
                        "interface_name": "backend_name1",
                        "status": "",
                    },
                    {
                        "ip_name": "127.0.0.1_ip_name",
                        "vlan": "other_vlan",
                        "ip_address": "127.0.0.1",
                        "mac_address": "01:01:01:01:01:01",
                        "interface_name": "mgmt_name2",
                        "status": "True",
                    }
                ],
                "laughing_man": [
                    {
                        "ip_name": "laughing_man_ip_name",
                        "vlan": "laughing_man_vlan",
                        "ip_address": "laughing_man_ip_address",
                        "mac_address": "laughing_man_mac_address",
                        "interface_name": "laughing_man_interface_name",
                        "status": "laughing_man_status",
                    },
                ],
                 "laughing_man_second_gig": [
                    {
                        "ip_name": "laughing_man_ip_name_second_gig",
                        "vlan": "laughing_man_vlan_second_gig",
                        "ip_address": "laughing_man_ip_address_second_gig",
                        "mac_address": "laughing_man_mac_address_second_gig",
                        "interface_name": "laughing_man_interface_name_second_gig",
                        "status": "laughing_man_status_second_gig",
                    },
                ]
           }}

        expected = {
            "arp": [
                {
                    "name": "127.0.0.1_ip_name",
                    "ip_address": "127.0.0.1",
                    "arp": [
                        {
                            "name": "laughing_man_ip_name",
                            "ip_address": "laughing_man_ip_address",
                            "arp": [
                                {
                                    "name": "laughing_man_ip_name_second_gig",
                                },
                            ],
                        },
                    ],
                }
            ]
        }
        
        dsm_model = {
            "title": "Name of DSM Model",
            "type": "dict",
            "description": "",
            "rbac": {"admin": {"read": True}},
            "nested": {
                "arp": {
                    "title": "Arp",
                    "type": "list",
                    "rbac": {"admin": {"read": True}},
                    "source": {
                        "type": "dn_lookup", "source": "input", "dn": "Domain.ARPS", "multi": True,
                        "filter_type": "dict_key_is_empty", "filter_args": {"key": "status"}
                    },
                    "nested": {
                        "name": {
                            "title": "Name",
                            "rbac": {"admin": {"read": True}},
                            "type": "string",
                            "source": {"type": "key_lookup",  "key": "ip_name"},
                        },
                        "ip_address": {
                            "title": "IP Address",
                            "type": "string",
                            "rbac": {"admin": {"read": True}},
                            "field_type": "ipv4_address",
                            "source": {"type": "key_lookup", "key": "ip_address"},
                        },
                         "arp": {
                            "title": "Arp",
                            "type": "list",
                            "rbac": {"admin": {"read": True}},
                            "source": {
                                "type": "dn_lookup", "source": "input", "dn": "Domain.laughing_man", "multi": True,
                            },
                            "nested": {
                                "name": {
                                    "title": "Name",
                                    "rbac": {"admin": {"read": True}},
                                    "type": "string",
                                    "source": {"type": "key_lookup",  "key": "ip_name"},
                                },
                                "ip_address": {
                                    "title": "IP Address",
                                    "type": "string",
                                    "rbac": {"admin": {"read": True}},
                                    "source": {"type": "key_lookup", "key": "ip_address"},
                                },
                                 "arp": {
                                    "title": "Arp",
                                    "type": "list",
                                    "rbac": {"admin": {"read": True}},
                                    "source": {
                                        "type": "dn_lookup", "source": "input", "dn": "Domain.laughing_man_second_gig", "multi": True,
                                    },
                                    "nested": {
                                        "name": {
                                            "title": "Name",
                                            "rbac": {"admin": {"read": True}},
                                            "type": "string",
                                            "source": {"type": "key_lookup",  "key": "ip_name"},
                                        },
                                    },
                                }
                            }
                        }
                    }
                }
            }
        }

        roles = ["admin",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_roles_rbac_restricted(self):
        input_data = {
            "items": [
                "interval 1",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there, I'm 4",
                "Thinking of another generic string five",
                "Last one boys, six"
            ]
        }

        expected = {}

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                "full": {"read": True},
                "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "foo": {"read": True},
                        "bar": {"read": True},
                    },
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "description": "options of counting items",
                    "item": {
                        "type": "string",
                        "example": "Random strings",
                    }
                }
            }
        }
        roles = ["restricted",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_roles_rbac_last_rbac(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        expected = {
            "options": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                "foo": {"read": True},
                "bar": {"read": True},
                "baz": {"read": True},
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "foo": {"read": True},
                        "bar": {"read": True},
                        "baz": {"read": True},
                    },
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "description": "",
                    "item": {
                        "type": "string",
                        "rbac": {
                            "foo": {"read": True},
                            "bar": {"read": True},
                            "baz": {"read": True},
                        },
                    }
                }
            }
        }

        roles = ["baz",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_roles_rbac_first_rbac(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        expected = {
            "options": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                "foo": {"read": True},
                "bar": {"read": True},
                "baz": {"read": True},
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "foo": {"read": True},
                        "bar": {"read": True},
                        "baz": {"read": True},
                    },
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "description": "",
                    "item": {
                        "type": "string",
                        "rbac": {
                            "foo": {"read": True},
                            "bar": {"read": True},
                            "baz": {"read": True},
                        },
                    }
                }
            }
        }

        roles = ["foo",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_roles_multiple_roles_per_level(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        expected = {
            "options": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                    "foo": {"read": True},
                    "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "bar": {"read": True},
                    },
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "description": "",
                    "item": {
                        "rbac": {
                            "baz": {"read": True},
                        },
                        "type": "string",
                    }
                }
            }
        }

        roles = ["foo", "bar", "baz"]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_roles_view_right_for_key_not_items_list_items(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        expected = {
            "options": [],
        }

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                    "foo": {"read": True},
                    "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "foo": {"read": True},
                    },
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "items"},
                    "description": "",
                    "item": {
                        "type": "string",
                    }
                }
            }
        }

        roles = ["foo", "bar", "baz"]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_rbac_roles_multiple_items_empty_result(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
            ]
        }

        expected = {}

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                    "full": {"read": True},
                    "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                    },  # rbac, is only for full ###
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "items"},
                    "description": "",
                    "item": {
                        "type": "string",
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                },
                "items": {
                    "title": "Items",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                    },
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "items"},
                    "description": "",
                    "item": {
                        "type": "string",
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                }
            }
        }

        roles = ["restricted",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_rbac_roles_multiple_items_empty_no_read_rbac_result(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
            ]
        }

        expected = {}

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                    "full": {"read": True},
                    "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "full": {"update": True},
                    },  # rbac, is only for full ###
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "items"},
                    "description": "",
                    "item": {
                        "type": "string",
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                },
                "items": {
                    "title": "Items",
                    "type": "list",
                    "rbac": {
                        "full": {"update": True},
                    },
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "items"},
                    "description": "",
                    "item": {
                        "type": "string",
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                }
            }
        }

        roles = ["full",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_rbac_roles_multiple_items_empty_single_result(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
            ]
        }

        expected = {
            "items": [
                "interval 10",
                "item that is in the second place",
            ],
        }

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                "full": {"read": True},
                "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                    }, # rbac, is only for full
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "items"},
                    "description": "",
                    "item": {
                        "type": "string",
                        "rbac": {
                            "full": {"read": True},
                        },
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                },
                "items": {
                    "title": "Items",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                        "restricted": {"read": True}
                    },
                    "source": {"type": "dn_lookup_loop", "source": "input", "dn": "items"},
                    "description": "",
                    "item": {
                        "type": "string",
                        "rbac": {
                            "full": {"read": True},
                            "restricted": {"read": True}
                        },

                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                }
            }
        }

        roles = ["restricted",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_rbac_roles_multiple_items_full(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
            ]
        }

        expected = {
            "items": [
                "interval 10",
                "item that is in the second place",
            ],
            "options": [
                "interval 10",
                "item that is in the second place",
            ]
        }

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "rbac": {
                "full": {"read": True},
                "restricted": {"read": True}
            },
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "rbac": {
                            "full": {"read": True},
                            "restricted": {"read": True}
                    },  # rbac, is only for full
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "description": "",
                    "item": {
                        "type": "string",
                        "rbac": {
                            "full": {"read": True},
                            "restricted": {"read": True}
                        },
                        "example": "",
                    }
                },
                "items": {
                    "title": "Items",
                    "type": "list",
                    "rbac": {
                        "full": {"read": True},
                        "restricted": {"read": True}
                    },
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "description": "",
                    "item": {
                        "type": "string",
                        "rbac": {
                            "full": {"read": True},
                            "restricted": {"read": True}
                        },
                        "example": "",
                    }
                }
            }
        }

        roles = ["full",]
        result = run_detail(dsm_model, roles=roles, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_postprocess(self):
        input_data = {
            "input_data":{
                "foo": {
                    "bar": {
                        "apple": [
                            ("apple_21", "20200629_105645"),
                            ("apple_22", "20200629_115655"),
                            ("apple_23", "20200629_125715"),
                        ]
                    }
                }
            }
        }
        expected = {
            "chart": [
                {
                    "value": "21",
                    "timestamp": "2020-06-29T10:56:45"
                },
                {
                    "value": "22",
                    "timestamp": "2020-06-29T11:56:55"
                },
                {
                    "value": "23",
                    "timestamp": "2020-06-29T12:57:15"
                },

            ]
        }

        dsm_model = {
            "title": "Name of DSM Model",
            "type": "dict",
            "description": "",
            "nested": {
                "chart": {
                    "title": "Chart",
                    "type": "list",
                    "source": {
                        "type": "dn_lookup",
                        "source": "input",
                        "multi": True,
                        "dn": "input_data.foo.bar.apple",
                    },
                    "nested": {
                        "value": {
                            "title": "Value",
                            "type": "string",
                            "source": {
                                "type": "index",
                                "index": 0,
                                "postformat": {
                                    "type": "regex_search",
                                    "regex": "(\d+)"
                                },
                            }
                        },
                        "timestamp": {
                            "title": "Timestamp",
                            "type": "string",
                            "field_type": "iso_timestamp",
                            "source": {
                                "type": "index",
                                "index": 1,
                                "postformat": {
                                    "type": "regex_to_iso_timestamp",
                                    "format": "%Y%m%d_%H%M%S"
                                    },
                            }
                        },
                    }
                }
            }
        }

        result = run_detail(dsm_model, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_postprocess_default(self):
        input_data = {
            "input_data":{
                "foo": {
                    "bar": {
                        "apple": [
                            ("apple_21", "20200629_105645"),
                            ("apple", "20200629_115655"),
                            ("apple_23", "20200629_125715"),
                        ]
                    }
                }
            }
        }
        expected = {
            "chart": [
                {
                    "value": "21",
                    "timestamp": "2020-06-29T10:56:45"
                },
                {
                    "value": "NaN",
                    "timestamp": "2020-06-29T11:56:55"
                },
                {
                    "value": "23",
                    "timestamp": "2020-06-29T12:57:15"
                },

            ]
        }

        dsm_model = {
            "title": "Name of DSM Model",
            "type": "dict",
            "description": "",
            "nested": {
                "chart": {
                    "title": "Chart",
                    "type": "list",
                    "source": {
                        "type": "dn_lookup",
                        "source": "input",
                        "multi": True,
                        "dn": "input_data.foo.bar.apple",
                    },
                    "nested": {
                        "value": {
                            "title": "Value",
                            "type": "string",
                            "source": {
                                "type": "index",
                                "index": 0,
                                "postformat": {
                                    "type": "regex_search",
                                    "regex": "(\d+)",
                                    "default": "NaN",
                                },
                            }
                        },
                        "timestamp": {
                            "title": "Timestamp",
                            "type": "string",
                            "field_type": "iso_timestamp",
                            "source": {
                                "type": "index",
                                "index": 1,
                                "postformat": {
                                    "type": "regex_to_iso_timestamp",
                                    "format": "%Y%m%d_%H%M%S"
                                    },
                            }
                        },
                    }
                }
            }
        }

        result = run_detail(dsm_model, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_errors_missing_type(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "nested": {
                "options": {
                    "title": "Options",
                    #  "type": "list"
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "description": "",
                    "item": {
                        "type": "string",
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                }
            }
        }

        with self.assertRaisesRegex(InvalidModel,  r"Missing 'type' on dn \('options',\)"):
            _ = run_detail(dsm_model, input=input_data)

    def test_basics_errors_missing_type_nested(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        dsm_model = {
            "title": "Monitor Options",
            "type": "dict",
            "description": "",
            "nested": {
                "options": {
                    "title": "Options",
                    "type": "list",
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "description": "",
                    "item": {
                        # "type": "string",
                        "example": "defaults-from HC4_OBOPRE_HTTP_PARENT",
                    }
                }
            }
        }

        with self.assertRaisesRegex(InvalidModel,  r"Missing 'type' on dn \('options',\)"):
            _ = run_detail(dsm_model, input=input_data)

    def test_basics_from_json(self):
        input_data = {
            "NAME": "Bob",
            "_AGE": 23,
            "FAVO": "blue",
        }

        expected = {
            "person": {
                "name": "Bob",
                "age": 23,
                "favorite_color": "blue",
            }
        }

        dsm_model = {
            "title": "Person View",
            "type": "dict",
            "description": "",
            "nested": {
                "person": {
                    "title": "Person",
                    "type": "dict",
                    "description": "",
                    "nested": {
                        "name": {
                            "title": "Name",
                            "type": "string",
                            "source": {"type": "json_key_item", "source": "input", "dn": "NAME"},
                            "example": "Bob",
                        },
                        "age": {
                            #"skip": True,
                            "title": "Age",
                            "type": "integer",
                            "source": {"type": "json_key_item", "source": "input", "dn": "_AGE"},
                            "example": "23",
                        },
                        "favorite_color": {
                            "title": "Favorite Color",
                            "type": "string",
                            "source": {"type": "json_key_item", "source": "input", "dn": "FAVO"},
                            "example": "",
                            }
                    }
                }
            }
        }

        result = run_detail(dsm_model, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_skip_item(self):
        input_data = {
            "NAME": "Bob",
            "_AGE": 23,
            "FAVO": "blue",
        }

        expected = {
            "person": {
                "name": "Bob",
                "favorite_color": "blue",
            }
        }

        dsm_model = {
            "title": "Person View",
            "type": "dict",
            "description": "",
            "nested": {
                "person": {
                    "title": "Person",
                    "type": "dict",
                    "description": "",
                    "nested": {
                        "name": {
                            "title": "Name",
                            "type": "string",
                            "source": {"type": "json_key_item", "source": "input", "dn": "NAME"},
                            "example": "Bob",
                        },
                        "age": {
                            "skip": True,
                            "title": "Age",
                            "type": "integer",
                            "source": {"type": "json_key_item", "source": "input", "dn": "_AGE"},
                            "example": "23",
                        },
                        "favorite_color": {
                            "title": "Favorite Color",
                            "type": "string",
                            "source": {"type": "json_key_item", "source": "input", "dn": "FAVO"},
                            "example": "",
                            }
                    }
                }
            }
        }

        result = run_detail(dsm_model, input=input_data)
        self.assertDictEqual(result, expected)


    def test_basics_skip_item(self):
        input_data = {
            "NAME": "Bob",
            "_AGE": 23,
            "FAVO": "blue",
        }

        expected = {
            "person": {
                "name": "Bob",
                "favorite_color": "blue",
            }
        }

        dsm_model = {
            "title": "Person View",
            "type": "dict",
            "description": "",
            "nested": {
                "person": {
                    "title": "Person",
                    "type": "dict",
                    "description": "",
                    "nested": {
                        "name": {
                            "title": "Name",
                            "type": "string",
                            "source": {"type": "json_key_item", "source": "input", "dn": "NAME"},
                            "example": "Bob",
                        },
                        "age": {
                            "skip": True,
                            "title": "Age",
                            "type": "integer",
                            "source": {"type": "json_key_item", "source": "input", "dn": "_AGE"},
                            "example": "23",
                        },
                        "favorite_color": {
                            "title": "Favorite Color",
                            "type": "string",
                            "source": {"type": "json_key_item", "source": "input", "dn": "FAVO"},
                            "example": "",
                            }
                    }
                }
            }
        }

        result = run_detail(dsm_model, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_use_default(self):
        input_data = {
            "NAME": "Bob",
            "_AGE": 23,
        }

        expected = {
            "person": {
                "name": "Bob",
                "favorite_color": "red",
            }
        }

        dsm_model = {
            "title": "Person View",
            "type": "dict",
            "description": "",
            "nested": {
                "person": {
                    "title": "Person",
                    "type": "dict",
                    "description": "",
                    "nested": {
                        "name": {
                            "title": "Name",
                            "type": "string",
                            "source": {"type": "json_key_item", "source": "input", "dn": "NAME"},
                            "example": "Bob",
                        },
                        "favorite_color": {
                            "title": "Favorite Color",
                            "type": "string",
                            "example": "blue",
                            "source": {"type": "json_key_item", "source": "input", "dn": "COLOR", "default": "red"},
                            }
                    }
                }
            }
        }

        result = run_detail(dsm_model, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_return_value(self):
        input_data = {}

        expected = {
            "person": {
                "name": "Peter Pan",
                "favorite_color": "Blue",
            }
        }

        dsm_model = {
            "title": "Person View",
            "type": "dict",
            "description": "",
            "nested": {
                "person": {
                    "title": "Person",
                    "type": "dict",
                    "description": "",
                    "nested": {
                        "name": {
                            "title": "Name",
                            "type": "string",
                            "source": {"type": "return_value", "value": "Peter Pan"},
                        },
                        "favorite_color": {
                            "title": "Favorite Color",
                            "type": "string",
                            "example": "blue",
                            "source": {"type": "return_value", "value": "Blue"},
                            }
                    }
                }
            }
        }

        result = run_detail(dsm_model, input=input_data)
        self.assertDictEqual(result, expected)

    def test_list_nodes(self):
        input_data = {
            "NAME": "Bob",
            "FAVO": "blue",
        }

        expected = [
            {
                "_dn": [
                    "person"
                ],
                "__columns": [
                    "name",
                    "favorite_color"
                ],
                "name": "Bob",
                "_name_dn": [
                    "person",
                    "name"
                ],
                "_name_type": "string",
                "favorite_color": "blue",
                "_favorite_color_dn": [
                    "person",
                    "favorite_color"
                ],
                "_favorite_color_type": "string"
            }
        ]

        dsm_model = {
            "title": "Person View",
            "type": "dict",
            "description": "",
            "nested": {
                "person": {
                    "title": "Person",
                    "type": "dict",
                    "description": "",
                    "nested": {
                        "name": {
                            "title": "Name",
                            "type": "string",
                            "source": {"type": "json_key_item", "source": "input", "dn": "NAME"},
                            "example": "Bob",
                        },
                        "age": {
                            "skip": True,
                            "title": "Age",
                            "type": "integer",
                            "source": {"type": "json_key_item", "source": "input", "dn": "_AGE"},
                            "example": "23",
                        },
                        "favorite_color": {
                            "title": "Favorite Color",
                            "type": "string",
                            "source": {"type": "json_key_item", "source": "input", "dn": "FAVO"},
                            "example": "",
                            }
                    }
                }
            }
        }

        result = list(run_nodes(dsm_model, input=input_data))

        self.assertEqual(result, expected)


class TestBasicsSources(unittest.TestCase):

    def test_basic_dn(self):

        expected = "find me"
        input_data = {
            "top": {
                "lower": {
                    "lowest": expected,
                }
            }
        }
        dn = "top.lower.lowest"
        result = get_by_dn(input_data, dn)
        self.assertEqual(result, expected)

    def test_basic_dn(self):
        expected = "find me"
        expected_found = True
        input_data = {
            "top": expected,
        }
        dn = "top"
        found_result, result = get_by_dn(input_data, dn)
        self.assertEqual(result, expected)
        self.assertEqual(found_result, expected_found)

    def test_basic_dn_not_found(self):
        expected = ""
        expected_found = False
        input_data = {
            "top": "can't find me with that dn",
        }
        dn = "top.lower.lowest"
        found_result, result = get_by_dn(input_data, dn)
        self.assertEqual(result, expected)
        self.assertEqual(found_result, expected_found)

    def test_basic_dn_nested(self):
        expected = "find me"
        expected_found = True
        input_data = {
            "top": {
                "lower": {
                    "lowest": expected,
                }
            }
        }
        dn = "top.lower.lowest"
        found_result, result = get_by_dn(input_data, dn)
        self.assertEqual(result, expected)
        self.assertEqual(found_result, expected_found)

    def test_basic_dn_nested_list(self):
        expected = "find me"
        expected_found = True
        input_data = {
            "top": {
                "lower": {
                    "list_with_items":[
                        expected,
                    ]
                }
            }
        }
        dn = "top.lower.list_with_items.[0]"
        found_result, result = get_by_dn(input_data, dn)
        self.assertEqual(result, expected)
        self.assertEqual(found_result, expected_found)

    def test_basic_dn_nested_list_second_item_not_found(self):
        expected = "don't find me"
        expected_found = True
        input_data = {
            "top": {
                "lower": {
                    "list_with_items":[
                        "find me",
                        "don't find me",
                        "also not me",
                    ]
                }
            }
        }
        dn = "top.lower.list_with_items.[1]"
        found_result, result = get_by_dn(input_data, dn)
        self.assertEqual(result, expected)
        self.assertEqual(found_result, expected_found)


    def test_basic_dn_nested_list_second_item(self):
        expected = "find me"
        expected_found = True
        input_data = {
            "top": {
                "lower": {
                    "list_with_items":[
                        "don't find me",
                        expected,
                        "also not me",
                    ]
                }
            }
        }
        dn = "top.lower.list_with_items.[1]"
        found_result, result = get_by_dn(input_data, dn)
        self.assertEqual(result, expected)
        self.assertEqual(found_result, expected_found)

    def test_basic_dn_nested_list_out_of_bound(self):
        expected = ""
        expected_found = False
        input_data = {
            "top": {
                "lower": {
                    "list_with_items":[
                        "don't find me",
                        expected,
                        "also not me",
                    ]
                }
            }
        }
        dn = "top.lower.list_with_items.[3]"
        found_result, result = get_by_dn(input_data, dn)
        self.assertEqual(result, expected)
        self.assertEqual(found_result, expected_found)

    def test_basic_dn_nested_list_second_item_nested(self):
        expected = "find me"
        expected_found = True
        input_data = {
            "top": {
                "lower": {
                    "list_with_items":[
                        "don't find me",
                        {
                            "another_key": expected,
                        },
                        "also not me",
                    ]
                }
            }
        }
        dn = "top.lower.list_with_items.[1].another_key"
        found_result, result = get_by_dn(input_data, dn)
        self.assertEqual(result, expected)
        self.assertEqual(found_result, expected_found)

    def test_basic_dn_nested_list_second_item_nested_yield(self):
        expected = ["find me", "find me two", "find me three"]
        input_data = {
            "top": {
                "lower": {
                    "list_with_items": [
                        "find me",
                        "find me two",
                        "find me three",
                    ]
                }
            }
        }
        dn = "top.lower.list_with_items"
        result = list(yield_by_dn(input_data, dn))
        self.assertEqual(result, expected)

    def test_iter_sources(self):
        input_data = [
            {
                "name": "apple",
                "values": {
                    'id_1': 'value_1',
                    'id_2': 'value_2',
                    'id_3': 'value_3',
                },
            }, {
                "name": "banana",
                'values': {
                    'id_1': 'value_a',
                    'id_2': 'value_b',
                    'id_3': 'value_c',
                }
            }, {
                "name": "citrus",
                'values': {
                    'id_1': 'value_d',
                    'id_2': 'value_e',
                    'id_3': 'value_f',
                }
            }
        ]

        expected = [
            {'apple': 'value_1', 'banana': 'value_a', 'citrus': 'value_d'},
            {'apple': 'value_2', 'banana': 'value_b', 'citrus': 'value_e'},
            {'apple': 'value_3', 'banana': 'value_c', 'citrus': 'value_f'},
        ]
        gather_args = {"key": "name", "dn_to_ids": "[0].values", "dn_to_values": "values", "source": "input_data"}
        result = list(iter_by_key(gather_args, model={}, dn_parent=("ok",), storage={"input": {"input_data": input_data}}))

        self.assertEqual(result, expected)


class TestBasicsListItem(unittest.TestCase):

    def test_basic_list_item(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        expected = [
            {'value': 'interval 10', 'dn': ('options', 'item'), 'title': None, 'description': None, 'type': 'string', 'field_type': None, 'searchable': True},
            {'value': 'item that is in the second place', 'dn': ('options', 'item'), 'title': None, 'description': None, 'type': 'string', 'field_type': None, 'searchable': True},
            {'value': 'the third one, if you will', 'dn': ('options', 'item'), 'title': None, 'description': None, 'type': 'string', 'field_type': None, 'searchable': True},
            {'value': 'Hi there', 'dn': ('options', 'item'), 'title': None, 'description': None, 'type': 'string', 'field_type': None, 'searchable': True},
            {'value': 'Thinking of another generic string', 'dn': ('options', 'item'), 'title': None, 'description': None, 'type': 'string', 'field_type': None, 'searchable': True},
            {'value': 'Last one boys', 'dn': ('options', 'item'), 'title': None, 'description': None, 'type': 'string', 'field_type': None, 'searchable': True},
        ]

        dsm_model = {
            "type": "dict",
            "nested": {
                "options": {
                    "type": "list",
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "item": {
                        "type": "string",
                    }
                }
            }
        }
        for i, item in enumerate(run_list(dsm_model, input=input_data)):
            self.assertDictEqual(expected[i],  item)

    def test_basic_list_item_extra_data(self):
        input_data = {
            "items": [
                "interval 10",
                "item that is in the second place",
                "the third one, if you will",
                "Hi there",
                "Thinking of another generic string",
                "Last one boys"
            ]
        }

        expected = [
            {'value': 'interval 10', 'dn': ('options', 'item'), 'title': "title field", 'description':  "description field", 'type': 'string', 'field_type': "text", 'searchable': True},
            {'value': 'item that is in the second place', 'dn': ('options', 'item'), 'title': "title field", 'description':  "description field", 'type': 'string', 'field_type': "text", 'searchable': True},
            {'value': 'the third one, if you will', 'dn': ('options', 'item'), 'title': "title field", 'description':  "description field", 'type': 'string', 'field_type': "text", 'searchable': True},
            {'value': 'Hi there', 'dn': ('options', 'item'), 'title': "title field", 'description':  "description field", 'type': 'string', 'field_type': "text", 'searchable': True},
            {'value': 'Thinking of another generic string', 'dn': ('options', 'item'), 'title': "title field", 'description':  "description field", 'type': 'string', 'field_type': "text", 'searchable': True},
            {'value': 'Last one boys', 'dn': ('options', 'item'), 'title': "title field", 'description':  "description field", 'type': 'string', 'field_type': "text", 'searchable': True},
        ]

        dsm_model = {
            "type": "dict",
            "nested": {
                "options": {
                    "type": "list",
                    "source": {"type": "json_key", "source": "input", "dn": "items", "multi": True},
                    "item": {
                        "description": "description field",
                        "field_type": "text",
                        "title": "title field",
                        "type": "string",
                    }
                }
            }
        }
        for i, item in enumerate(run_list(dsm_model, input=input_data)):
            self.assertDictEqual(expected[i],  item)

    def test_basic_list_items(self):
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

        expected = [
            {'value': 5164.23076923, 'dn': ('item',), 'title': 'counter', 'description': None, 'type': 'string', 'field_type': 'float', 'searchable': True, 'searchable': True},
            {'value': '2020-03-26T15:00:00Z', 'dn': ('item',), 'title': 'timestamp', 'description': None, 'type': 'string', 'field_type': None, 'searchable': True, 'searchable': True},
            {'value': 5164.23076924, 'dn': ('item',), 'title': 'counter', 'description': None, 'type': 'string', 'field_type': 'float', 'searchable': True, 'searchable': True},
            {'value': '2020-03-26T15:00:01Z', 'dn': ('item',), 'title': 'timestamp', 'description': None, 'type': 'string', 'field_type': None, 'searchable': True, 'searchable': True},
        ]


        dsm_model = {
            "type": "list",
            "source": {"type": "loop_over", "source": "input", "dn": ""},
            "items": [

                {
                    "title": "counter",
                    "type": "string",
                    "field_type": "float",
                    "source": {"type": "index", "index": 1},
                },
                {
                    "title": "timestamp",
                    "type": "string",
                    "source": {"type": "index", "index": 0},
                },
            ]
        }

        for i, item in enumerate(run_list(dsm_model, input=input_data)):
            self.assertDictEqual(expected[i],  item)

    def test_basic_list_items_extra_fields(self):
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

        expected = [
            {'value': 5164.23076923, 'dn': ('item',), 'title': 'counter', 'description': "float indicating amount", 'type': 'string', 'field_type': 'float', 'searchable': True},
            {'value': '2020-03-26T15:00:00Z', 'dn': ('item',), 'title': 'timestamp', 'description': "iso", 'type': 'string', 'field_type': "iso_timestamp", 'searchable': True},
            {'value': 5164.23076924, 'dn': ('item',), 'title': 'counter', 'description': "float indicating amount", 'type': 'string', 'field_type': 'float', 'searchable': True},
            {'value': '2020-03-26T15:00:01Z', 'dn': ('item',), 'title': 'timestamp', 'description': "iso", 'type': 'string', 'field_type': "iso_timestamp", 'searchable': True},
        ]

        dsm_model = {
            "type": "list",
            "source": {"type": "loop_over", "source": "input", "dn": ""},
            "items": [

                {
                    "title": "counter",
                    "description": "float indicating amount",
                    "type": "string",
                    "field_type": "float",
                    "source": {"type": "index", "index": 1},
                },
                {
                    "title": "timestamp",
                    "description": "iso",
                    "field_type": "iso_timestamp",
                    "type": "string",
                    "source": {"type": "index", "index": 0},
                },
            ]
        }

        for i, item in enumerate(run_list(dsm_model, input=input_data)):
            self.assertDictEqual(expected[i],  item)

    def test_basic_list_dict(self):
        input_data = {
            "NAME": "Bob",
            "_AGE": 23,
            "FAVO": "blue",
        }

        expected = [
            {'value': 'Bob', 'dn': ('person', 'name'), 'title': 'Name', 'description': None, 'type': 'string', 'field_type': None, 'searchable': True},
            {'value': 23, 'dn': ('person', 'age'), 'title': 'Age', 'description': None, 'type': 'integer', 'field_type': None, 'searchable': True},
            {'value': 'blue', 'dn': ('person', 'favorite_color'), 'title': 'Favorite Color', 'description': None, 'type': 'string', 'field_type': None, 'searchable': True},
        ]

        dsm_model = {
            "title": "Person View",
            "type": "dict",
            "description": "",
            "nested": {
                "person": {
                    "title": "Person",
                    "type": "dict",
                    "description": "",
                    "nested": {
                        "name": {
                            "title": "Name",
                            "type": "string",
                            "source": {"type": "json_key_item", "source": "input", "dn": "NAME"},
                            "example": "Bob",
                        },
                        "age": {
                            #"skip": True,
                            "title": "Age",
                            "type": "integer",
                            "source": {"type": "json_key_item", "source": "input", "dn": "_AGE"},
                            "example": "23",
                        },
                        "favorite_color": {
                            "title": "Favorite Color",
                            "type": "string",
                            "source": {"type": "json_key_item", "source": "input", "dn": "FAVO"},
                            "example": "",
                        }
                    }
                }
            }
        }

        for i, item in enumerate(run_list(dsm_model, input=input_data)):
            self.assertDictEqual(expected[i],  item)

    def test_basic_list_dict_extra_fields(self):
        input_data = {
            "NAME": "Bob",
            "_AGE": 23,
            "FAVO": "blue",
        }

        expected = [
            {'value': 'Bob', 'dn': ('person', 'name'), 'title': 'Name', 'description':  "Name of Person", 'type': 'string', 'field_type': "first_name", 'searchable': True},
            {'value': 23, 'dn': ('person', 'age'), 'title': 'Age', 'description': "Date of birth till now, in years.", 'type': 'integer', 'field_type': "human_age", 'searchable': True},
            {'value': 'blue', 'dn': ('person', 'favorite_color'), 'title': 'Favorite Color', 'description': "Favorite color of person", 'type': 'string', 'field_type': "color_name", 'searchable': True},
        ]

        dsm_model = {
            "title": "Person View",
            "type": "dict",
            "description": "",
            "nested": {
                "person": {
                    "title": "Person",
                    "type": "dict",
                    "description": "",
                    "nested": {
                        "name": {
                            "title": "Name",
                            "type": "string",
                            "field_type": "first_name",
                            "source": {"type": "json_key_item", "source": "input", "dn": "NAME"},
                            "description": "Name of Person",
                            "example": "Bob",
                        },
                        "age": {
                            #"skip": True,
                            "title": "Age",
                            "field_type": "human_age",
                            "type": "integer",
                            "source": {"type": "json_key_item", "source": "input", "dn": "_AGE"},
                            "description": "Date of birth till now, in years.",
                            "example": "23",
                        },
                        "favorite_color": {
                            "title": "Favorite Color",
                            "type": "string",
                            "field_type": "color_name",
                            "source": {"type": "json_key_item", "source": "input", "dn": "FAVO"},
                            "description": "Favorite color of person",
                            "example": "red",
                        }
                    }
                }
            }
        }

        for i, item in enumerate(run_list(dsm_model, input=input_data)):
            self.assertDictEqual(expected[i],  item)

    def test_basic_list_dict_extra_fields_skipped(self):
        input_data = {
            "NAME": "Bob",
            "_AGE": 23,
            "FAVO": "blue",
        }

        expected = [
            {'value': 'Bob', 'dn': ('person', 'name'), 'title': 'Name', 'description':  "Name of Person", 'type': 'string', 'field_type': "first_name", 'searchable': True},
            {'value': 'blue', 'dn': ('person', 'favorite_color'), 'title': 'Favorite Color', 'description': "Favorite color of person", 'type': 'string', 'field_type': "color_name", 'searchable': True},
        ]

        dsm_model = {
            "title": "Person View",
            "type": "dict",
            "description": "",
            "nested": {
                "person": {
                    "title": "Person",
                    "type": "dict",
                    "description": "",
                    "nested": {
                        "name": {
                            "title": "Name",
                            "type": "string",
                            "field_type": "first_name",
                            "source": {"type": "json_key_item", "source": "input", "dn": "NAME"},
                            "description": "Name of Person",
                            "example": "Bob",
                        },
                        "age": {
                            "skip": True,
                            "title": "Age",
                            "field_type": "human_age",
                            "type": "integer",
                            "source": {"type": "json_key_item", "source": "input", "dn": "_AGE"},
                            "description": "Date of birth till now, in years.",
                            "example": "23",
                        },
                        "favorite_color": {
                            "title": "Favorite Color",
                            "type": "string",
                            "field_type": "color_name",
                            "source": {"type": "json_key_item", "source": "input", "dn": "FAVO"},
                            "description": "Favorite color of person",
                            "example": "red",
                        }
                    }
                }
            }
        }

        for i, item in enumerate(run_list(dsm_model, input=input_data)):
            self.assertDictEqual(expected[i],  item)


class TestBasicSource(unittest.TestCase):

    def test_basics(self):
        input_data = {
            "foo": "bar"
        }

        expected = {
            "baz": "bar"
        }

        dsm_model = {
            "type": "dict",
            "nested": {
                "baz": {
                    "type": "str",
                    "source": {"type": "get_from_source", "source": "input", "dn": "foo"},
                    "item": {
                        "type": "string",
                    }
                }
            }
        }
        result = run_detail(dsm_model, input=input_data)
        self.assertDictEqual(result, expected)

    def test_basics_missing_dn(self):
        input_data = {
            "foo": "bar"
        }

        dsm_model = {
            "type": "dict",
            "nested": {
                "baz": {
                    "type": "str",
                    "source": {"type": "get_from_source", "source": "input"},
                    "item": {
                        "type": "string",
                    }
                }
            }
        }
        with self.assertRaisesRegex(InvalidModel,  r"Missing 'dn' in source  get_from_source with dn: \('baz',\)"):
            _ = run_detail(dsm_model, input=input_data)

    def test_basics_error_on_model(self):
        input_data = {
            "foo": "bar"
        }

        dsm_model = {
            "type": "dict",
            "nested": {
                "baz": {
                    "type": "list",
                    "source": {
                        "type": "get_from_source",
                        "source": "input",
                        "dn": "foo",
                    },
                    "items": { # Error
                        "type": "string",
                        "source": {
                            "type": "key_lookup",
                            "dn": "missing"
                        }
                    }
                }
            }
        }
        with self.assertRaisesRegex(InvalidModel, r"Error while getting 'type' on dn \('baz',\): string indices must be integers"):
            _ = run_detail(dsm_model, input=input_data)

    def test_basics_error_on_model_loop_over_none(self):
        input_data = {
            "foo": None
        }

        dsm_model = {
            "type": "dict",
            "nested": {
                "baz": {
                    "type": "list",
                    "source": {
                        "type": "get_from_source",
                        "source": "input",
                        "dn": "foo",
                    },
                    "nested": {
                        "type": "string",
                        "source": {
                            "type": "key_lookup",
                            "dn": "missing"
                        }
                    }
                }
            }
        }
        with self.assertRaisesRegex(InvalidModel, r"Error while gathering data, on dn \('baz',\), reason: 'NoneType' object is not iterable"):
            _ = run_detail(dsm_model, input=input_data)
            print(_)


if __name__ == "__main__":
    unittest.main()
