# (c) Bob Vanhoof
# MICAS - ESAT - KULEUVEN
# 02/03/2021

import debug
import pdb
from bitcell_array import bitcell_array
from bitcell_base_array import bitcell_base_array
from globals import OPTS

class bitcell_array_lp(bitcell_array):
    def __init__(self, rows, cols, column_offset=0, name=""):
        bitcell_base_array.__init__(self,rows=rows, cols=cols, column_offset=column_offset, name=name)
        debug.info(1, "Creating {0} {1} x {2}".format(self.name, rows, cols))
        self.add_comment("rows: {0} cols: {1}".format(rows, cols))

        self.vdd_names = []
        self.create_all_vdd_names()
        self.vdd_routing_layer = "m3"
        # This will create a default set of bitline/wordline names
        self.create_all_bitline_names()
        self.create_all_wordline_names()

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
        for bl_name in self.get_bitline_names():
            self.add_pin(bl_name, "INOUT")
        for wl_name in self.get_wordline_names():
            self.add_pin(wl_name, "INPUT")
        for vdd_name in self.get_vdd_names():
            self.add_pin(vdd_name, "POWER")
        self.add_pin("gnd", "GROUND")
    
    def get_bitcell_pins(self, row, col):
        bitcell_pins = []
        for port in self.all_ports:
            bitcell_pins.extend([x for x in self.get_bitline_names(port) if x.endswith("_{0}".format(col))])
        bitcell_pins.extend([x for x in self.all_wordline_names if x.endswith("_{0}".format(row))])
        bitcell_pins.extend([x for x in self.get_vdd_names() if x.endswith("_{0}".format(row>>1))])
        bitcell_pins.append("gnd")
        return bitcell_pins

    def create_layout(self):

        self.place_array("bit_r{0}_c{1}")
      
        self.add_vdd_stripes()

        self.add_layout_pins()

        self.add_boundary()

        self.DRC_LVS()

    def add_vdd_stripes(self):
        rs = (self.row_size>>1) + self.row_size%2
        for row in range(rs):
            vdd_names = "vdd"
            vdd_pin = self.cell_inst[row*2, 0].get_pin(vdd_names)
            self.add_rect( layer=self.vdd_routing_layer,
                           offset=vdd_pin.ll().scale(0, 1),
                           width=self.width,
                           height=vdd_pin.height())
        if self.vdd_routing_layer == "m3":
            for cell in self.cell_inst.values():
                self.add_via_center(['m2','via2',self.vdd_routing_layer],cell.get_pin('vdd').center())
#        pdb.set_trace()


    def add_layout_pins(self):
        """ Add the layout pins """
        bitline_names = self.cell.get_all_bitline_names()
        for col in range(self.column_size):
            for port in self.all_ports:
                bl_pin = self.cell_inst[0, col].get_pin(bitline_names[2 * port])
                self.add_layout_pin(text="bl_{0}_{1}".format(port, col),
                                    layer=bl_pin.layer,
                                    offset=bl_pin.ll().scale(1, 0),
                                    width=bl_pin.width(),
                                    height=self.height)
                br_pin = self.cell_inst[0, col].get_pin(bitline_names[2 * port + 1])
                self.add_layout_pin(text="br_{0}_{1}".format(port, col),
                                    layer=br_pin.layer,
                                    offset=br_pin.ll().scale(1, 0),
                                    width=br_pin.width(),
                                    height=self.height)

        wl_names = self.cell.get_all_wl_names()
        for row in range(self.row_size):
            for port in self.all_ports:
                wl_pin = self.cell_inst[row, 0].get_pin(wl_names[port])
                self.add_layout_pin(text="wl_{0}_{1}".format(port, row),
                                    layer=wl_pin.layer,
                                    offset=wl_pin.ll().scale(0, 1),
                                    width=self.width,
                                    height=wl_pin.height())

        # propagate vdd pin
        rs = (self.row_size>>1) + self.row_size%2
        for row in range(rs):
            vdd_names = "vdd"
            vdd_pin = self.cell_inst[row*2, 0].get_pin(vdd_names)
            self.add_layout_pin(text="vdd_{0}".format(row),
                                    layer=self.vdd_routing_layer,
                                    offset=vdd_pin.ll().scale(0, 1),
                                    width=self.width,
                                    height=vdd_pin.height())
            

        # Copy a gnd layout pin from every cell
        for row in range(self.row_size):
            for col in range(self.column_size):
                inst = self.cell_inst[row, col]
                for pin_name in ["gnd"]:
                    self.copy_layout_pin(inst, pin_name)
