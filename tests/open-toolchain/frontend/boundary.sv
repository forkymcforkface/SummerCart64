/* Fixture: an unqualified interface controls a physical open-drain inout. */
interface sb;
 logic enable;
endinterface
module child(sb control, inout wire pad);
 assign pad=control.enable?1'b0:1'bz;
endmodule
module top(input enable,inout wire pad,output wire floating);
 sb control();
 assign control.enable=enable;
 child c(control,pad);
 assign floating=1'bz;
endmodule
