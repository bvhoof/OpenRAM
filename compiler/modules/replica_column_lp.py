# (c) Bob Vanhoof
# MICAS - ESAT - KU LEUVEN
# 02/03/2021

import debug
from replica_column import replica_column
from bitcell_base_array import bitcell_base_array
from sram_factory import factory
from globals import OPTS
from tech import layer_properties as layer_props


class replica_column_lp(replica_column):
    
    def __init__(self, name, rows, rbl, replica_bit, column_offset=0):
        # Used for pin names and properties
        self.cell = factory.create(module_type=OPTS.bitcell)
        # Row size is the number of rows with word lines
        self.row_size = sum(rbl) + rows
        # Start of regular word line rows
        self.row_start = rbl[0] + 1
        # End of regular word line rows
        self.row_end = self.row_start + rows
        if not self.cell.end_caps:
            self.row_size += 2
        bitcell_base_array.__init__(self,rows=self.row_size, cols=1, column_offset=column_offset, name=name)

        self.rows = rows
        self.left_rbl = rbl[0]
        self.right_rbl = rbl[1]
        self.replica_bit = replica_bit

        # Total size includes the replica rows and column cap rows
        self.total_size = self.left_rbl + rows + self.right_rbl + 2

        self.column_offset = column_offset

        debug.check(replica_bit != 0 and replica_bit != self.total_size - 1,
                    "Replica bit cannot be the dummy/cap row.")
        debug.check(replica_bit < self.row_start or replica_bit >= self.row_end,
                    "Replica bit cannot be in the regular array.")
        if layer_props.replica_column.even_rows:
            debug.check(rows % 2 == 0 and (self.left_rbl + 1) % 2 == 0,
                        "sky130 currently requires rows to be even and to start with X mirroring"
                        + " (left_rbl must be odd) for LVS.")

        self.vdd_routing_layer = "m3"
        
        self.vdd_names = []
        self.create_all_vdd_names()
        self.create_all_bitline_names()
        self.create_all_wordline_names(self.row_size)

        self.create_netlist()
        if not OPTS.netlist_only:
            self.create_layout()



    def create_all_vdd_names(self, row_size=None):
        if row_size == None:
            row_size = self.row_size
        rs = (row_size>>1) + row_size%2
        for row in range(rs):
            self.vdd_names.append("vdd_{0}".format(row))

    def get_vdd_names(self):
        return self.vdd_names

    def add_pins(self):
        self.add_pin_list(self.all_bitline_names, 'INOUT')
        self.add_pin_list(self.all_wordline_names, 'INPUT')
        self.add_pin_list(self.get_vdd_names(), 'POWER')
        self.add_pin('gnd','GROUND')

    def get_bitcell_pins(self, row, col):
        bitcell_pins = []
        for port in self.all_ports:
            bitcell_pins.extend([x for x in self.get_bitline_names(port) if x.endswith("_{0}".format(col))])
        bitcell_pins.extend([x for x in self.all_wordline_names if x.endswith("_{0}".format(row))])
        bitcell_pins.extend([x for x in self.get_vdd_names() if x.endswith("_{0}".format(row>>1))])
        bitcell_pins.append("gnd")
        return bitcell_pins

    def create_layout(self):
        self.place_instances()

        self.height = self.cell_inst[-1].uy()
        self.width = self.cell_inst[0].rx()

        self.add_vdd_stripes()

        self.add_layout_pins()

        self.add_boundary()
        self.DRC_LVS()

    def add_vdd_stripes(self):
        rs = (self.row_size>>1) + self.row_size%2
        for row in range(rs):
            vdd_names = "vdd"
            vdd_pin = self.cell_inst[row*2].get_pin(vdd_names)
            self.add_rect( layer=self.vdd_routing_layer,
                           offset=vdd_pin.ll().scale(0, 1),
                           width=self.width,
                           height=vdd_pin.height())
        if self.vdd_routing_layer == "m3":
            for cell in self.cell_inst:
                self.add_via_center(['m2','via2',self.vdd_routing_layer],cell.get_pin('vdd').center())


    def add_layout_pins(self):
        """ Add the layout pins """
        for port in self.all_ports:
            bl_pin = self.cell_inst[0].get_pin(self.cell.get_bl_name(port))
            self.add_layout_pin(text="bl_{0}_{1}".format(port, 0),
                                layer=bl_pin.layer,
                                offset=bl_pin.ll().scale(1, 0),
                                width=bl_pin.width(),
                                height=self.height)
            bl_pin = self.cell_inst[0].get_pin(self.cell.get_br_name(port))
            self.add_layout_pin(text="br_{0}_{1}".format(port, 0),
                                layer=bl_pin.layer,
                                offset=bl_pin.ll().scale(1, 0),
                                width=bl_pin.width(),
                                height=self.height)

        if self.cell.end_caps:
            row_range_max = self.total_size - 1
            row_range_min = 1
        else:
            row_range_max = self.total_size
            row_range_min = 0

        for port in self.all_ports:
            for row in range(row_range_min, row_range_max):
                wl_pin = self.cell_inst[row].get_pin(self.cell.get_wl_name(port))
                self.add_layout_pin(text="wl_{0}_{1}".format(port, row - row_range_min),
                                    layer=wl_pin.layer,
                                    offset=wl_pin.ll().scale(0, 1),
                                    width=self.width,
                                    height=wl_pin.height())

        rs = (self.row_size>>1) + self.row_size%2
        for row in range(rs):
            vdd_names = "vdd"
            vdd_pin = self.cell_inst[row*2].get_pin(vdd_names)
            self.add_layout_pin(text="vdd_{0}".format(row),
                                    layer=self.vdd_routing_layer,
                                    offset=vdd_pin.ll().scale(0, 1),
                                    width=self.width,
                                    height=vdd_pin.height())

        # Supplies are only connected in the ends
        for (index, inst) in enumerate(self.cell_inst):
            for pin_name in ["gnd"]:
                if inst in [self.cell_inst[0], self.cell_inst[self.total_size - 1]]:
                    for pin in inst.get_pins(pin_name):
                        self.copy_power_pin(pin)
                else:
                    self.copy_layout_pin(inst, pin_name)


