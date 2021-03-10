# (c) Bob Vanhoof
# MICAS - ESAT - KU LEUVEN
# 02/03/2021

import debug
from replica_bitcell_array import replica_bitcell_array
from bitcell_base_array import bitcell_base_array
from globals import OPTS
from sram_factory import factory

class replica_bitcell_array_lp(replica_bitcell_array):
    """
    Creates a bitcell arrow of cols x rows and then adds the replica
    and dummy columns and rows.  Replica columns are on the left and
    right, respectively and connected to the given bitcell ports.
    Dummy are the outside columns/rows with WL and BL tied to gnd.
    Requires a regular bitcell array, replica bitcell, and dummy
    bitcell (Bl/BR disconnected).
    """
    def __init__(self, rows, cols, rbl=None, left_rbl=None, right_rbl=None, name=""):
        bitcell_base_array.__init__(self,name, rows, cols, column_offset=0)
        debug.info(1, "Creating {0} {1} x {2} rbls: {3} left_rbl: {4} right_rbl: {5}".format(self.name,
                                                                                             rows,
                                                                                             cols,
                                                                                             rbl,
                                                                                             left_rbl,
                                                                                             right_rbl))
        self.add_comment("rows: {0} cols: {1}".format(rows, cols))
        self.add_comment("rbl: {0} left_rbl: {1} right_rbl: {2}".format(rbl, left_rbl, right_rbl))

        self.column_size = cols
        self.row_size = rows
        # This is how many RBLs are in all the arrays
        if rbl:
            self.rbl = rbl
        else:
            self.rbl=[1, 1 if len(self.all_ports)>1 else 0]
        # This specifies which RBL to put on the left or right
        # by port number
        # This could be an empty list
        if left_rbl != None:
            self.left_rbl = left_rbl
        else:
            self.left_rbl = [0]
        # This could be an empty list
        if right_rbl != None:
            self.right_rbl = right_rbl
        else:
            self.right_rbl=[1] if len(self.all_ports) > 1 else []
        self.rbls = self.left_rbl + self.right_rbl

        debug.check(sum(self.rbl) == len(self.all_ports),
                    "Invalid number of RBLs for port configuration.")
        debug.check(sum(self.rbl) >= len(self.left_rbl) + len(self.right_rbl),
                    "Invalid number of RBLs for port configuration.")

        # Two dummy rows plus replica even if we don't add the column
        self.extra_rows = sum(self.rbl)
        # Two dummy cols plus replica if we add the column
        self.extra_cols = len(self.left_rbl) + len(self.right_rbl)

        # If we aren't using row/col caps, then we need to use the bitcell
        if not self.cell.end_caps:
            self.extra_rows += 2
            self.extra_cols += 2
        
        # add vdd names
        self.vdd_names = []
        self.create_all_vdd_names(self.row_size+self.extra_rows)        

        self.create_netlist()
        if not OPTS.netlist_only:
            self.create_layout()

        # We don't offset this because we need to align
        # the replica bitcell in the control logic
        # self.offset_all_coordinates()

    def create_all_vdd_names(self, row_size=None):
        if row_size == None:
            row_size = self.row_size
        rs = (row_size>>1) + row_size%2
        for row in range(rs):
            self.vdd_names.append("vdd_{0}".format(row))

    def get_vdd_names(self):
        return self.vdd_names
    
    def add_modules(self):
        """ Similar to the super class, but with different modules to facilitate row-based voltage switching
        """
        
        # Bitcell array
        self.bitcell_array = factory.create(module_type="bitcell_array_lp",
                                            column_offset=1 + len(self.left_rbl),
                                            cols=self.column_size,
                                            rows=self.row_size)
        self.add_mod(self.bitcell_array)

        # Replica bitlines
        self.replica_columns = {}

        for port in self.all_ports:
            if port in self.left_rbl:
                # We will always have self.rbl[0] rows of replica wordlines below
                # the array.
                # These go from the top (where the bitcell array starts ) down
                replica_bit = self.rbl[0] - port
                column_offset = self.rbl[0]

            elif port in self.right_rbl:

                # We will always have self.rbl[0] rows of replica wordlines below
                # the array.
                # These go from the bottom up
                replica_bit = self.rbl[0] + self.row_size + port
                column_offset = self.rbl[0] + self.column_size + 1
            else:
                continue

            self.replica_columns[port] = factory.create(module_type="replica_column_lp",
                                                        rows=self.row_size,
                                                        rbl=self.rbl,
                                                        column_offset=column_offset,
                                                        replica_bit=replica_bit)
            self.add_mod(self.replica_columns[port])

        # Dummy row
        self.dummy_row = factory.create(module_type="dummy_array_lp",
                                            cols=self.column_size,
                                            rows=1,
                                            # dummy column + left replica column
                                            column_offset=1 + len(self.left_rbl),
                                            mirror=0)
        self.add_mod(self.dummy_row)

        # Dummy Row or Col Cap, depending on bitcell array properties
        col_cap_module_type = ("col_cap_array" if self.cell.end_caps else "dummy_array_lp")
        self.col_cap_top = factory.create(module_type=col_cap_module_type,
                                          cols=self.column_size,
                                          rows=1,
                                          # dummy column + left replica column(s)
                                          column_offset=1 + len(self.left_rbl),
                                          mirror=0,
                                          location="top")
        self.add_mod(self.col_cap_top)

        self.col_cap_bottom = factory.create(module_type=col_cap_module_type,
                                             cols=self.column_size,
                                             rows=1,
                                             # dummy column + left replica column(s)
                                             column_offset=1 + len(self.left_rbl),
                                             mirror=0,
                                             location="bottom")
        self.add_mod(self.col_cap_bottom)

        # Dummy Col or Row Cap, depending on bitcell array properties
        row_cap_module_type = ("row_cap_array" if self.cell.end_caps else "dummy_array_lp")

        self.row_cap_left = factory.create(module_type=row_cap_module_type,
                                            cols=1,
                                            column_offset=0,
                                            rows=self.row_size + self.extra_rows,
                                            mirror=(self.rbl[0] + 1) % 2)
        self.add_mod(self.row_cap_left)

        self.row_cap_right = factory.create(module_type=row_cap_module_type,
                                            cols=1,
                                            #   dummy column
                                            # + left replica column(s)
                                            # + bitcell columns
                                            # + right replica column(s)
                                            column_offset=1 + len(self.left_rbl) + self.column_size + self.rbl[0],
                                            rows=self.row_size + self.extra_rows,
                                            mirror=(self.rbl[0] + 1) %2)
        self.add_mod(self.row_cap_right)



    def add_pins(self):

        # Arrays are always:
        # bitlines (column first then port order)
        # word lines (row first then port order)
        # dummy wordlines
        # replica wordlines
        # regular wordlines (bottom to top)
        # # dummy bitlines
        # replica bitlines (port order)
        # regular bitlines (left to right port order)
        #
        # vdd
        # gnd

        self.add_bitline_pins()
        self.add_wordline_pins()
#        self.add_pin("vdd", "POWER")
        for vdd_name in self.get_vdd_names():
            self.add_pin(vdd_name, "POWER")
        self.add_pin("gnd", "GROUND")

    def create_instances(self):
        """ Create the module instances used in this design """
        self.supplies = ["gnd"]
        if len(self.all_ports) == 1:
            supply_names = self.get_vdd_names()[1:]
        else:
            supply_names = self.get_vdd_names()[1:-2]

        # Used for names/dimensions only
        self.cell = factory.create(module_type=OPTS.bitcell)

        # Main array
        self.bitcell_array_inst=self.add_inst(name="bitcell_array",
                                                mod=self.bitcell_array)
        self.connect_inst(self.all_bitline_names + self.all_wordline_names + supply_names + self.supplies)

        # Replica columns
        self.replica_col_insts = []
        for port in self.all_ports:
            if port in self.rbls:
                self.replica_col_insts.append(self.add_inst(name="replica_col_{}".format(port),
                                                            mod=self.replica_columns[port]))
                self.connect_inst(self.rbl_bitline_names[port] + self.replica_array_wordline_names + self.get_vdd_names() + self.supplies)
            else:
                self.replica_col_insts.append(None)

        # Dummy rows under the bitcell array (connected with with the replica cell wl)
        self.dummy_row_replica_insts = []
        # Note, this is the number of left and right even if we aren't adding the columns to this bitcell array!
        supply_names = [self.get_vdd_names()[i] for i in [0,-2]]
        for port in self.all_ports:
            self.dummy_row_replica_insts.append(self.add_inst(name="dummy_row_{}".format(port),
                                                                mod=self.dummy_row))
            self.connect_inst(self.all_bitline_names + [x if x not in self.gnd_wordline_names else "gnd" for x in self.rbl_wordline_names[port]] + [supply_names[port]] + self.supplies)

        # Top/bottom dummy rows or col caps
        self.dummy_row_insts = []
        self.dummy_row_insts.append(self.add_inst(name="dummy_row_bot",
                                                  mod=self.col_cap_bottom))
        self.connect_inst(self.all_bitline_names + ["gnd"] * len(self.col_cap_bottom.get_wordline_names()) + [self.get_vdd_names()[0]] + self.supplies)
        self.dummy_row_insts.append(self.add_inst(name="dummy_row_top",
                                                  mod=self.col_cap_top))
        self.connect_inst(self.all_bitline_names + ["gnd"] * len(self.col_cap_top.get_wordline_names()) + [self.get_vdd_names()[-1]] + self.supplies)

        # Left/right Dummy columns
        self.dummy_col_insts = []
        self.dummy_col_insts.append(self.add_inst(name="dummy_col_left",
                                                    mod=self.row_cap_left))
        self.connect_inst(["dummy_left_" + bl for bl in self.row_cap_left.all_bitline_names] + self.replica_array_wordline_names + self.get_vdd_names() + self.supplies)
        self.dummy_col_insts.append(self.add_inst(name="dummy_col_right",
                                                    mod=self.row_cap_right))
        self.connect_inst(["dummy_right_" + bl for bl in self.row_cap_right.all_bitline_names] + self.replica_array_wordline_names + self.get_vdd_names() + self.supplies)

    def add_layout_pins(self):
        super().add_layout_pins()
        
        # copy all the vdd's 
        for pin_name in self.get_vdd_names():
            for inst in self.dummy_col_insts:
                pin_list = inst.get_pins(pin_name)
                for pin in pin_list:
                    self.copy_power_pin(pin)


