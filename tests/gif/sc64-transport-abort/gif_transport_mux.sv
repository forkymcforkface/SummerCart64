/* Experimental CFG upstream mux. A grant owns one complete request; a low
 * request/ACK gap separates grants, including DMA masters retaining request. */
module gif_transport_mux (
    input logic clk,reset,
    output logic idle,
    mem_bus.memory scratch,source,packet,
    mem_bus.controller memory
);
    typedef enum logic [1:0] { FREE,ACTIVE,GAP } state_t;
    state_t state;
    logic [1:0] owner,next_owner,choice;
    logic found;
    always_comb begin
        found=1'b0;choice=0;
        for(integer offset=0;offset<3;offset=offset+1) begin
            if(!found) begin
                case((int'(next_owner)+offset)%3)
                    0:if(scratch.request)begin found=1;choice=0;end
                    1:if(source.request)begin found=1;choice=1;end
                    2:if(packet.request)begin found=1;choice=2;end
                    default:begin end
                endcase
            end
        end
        scratch.ack=state==ACTIVE&&owner==0&&memory.ack;
        source.ack=state==ACTIVE&&owner==1&&memory.ack;
        packet.ack=state==ACTIVE&&owner==2&&memory.ack;
        scratch.rdata=memory.rdata;source.rdata=memory.rdata;packet.rdata=memory.rdata;
        memory.request=state==ACTIVE;
        idle=state==FREE&&!memory.ack;
    end
    always_ff @(posedge clk) begin
        if(reset)begin state<=FREE;next_owner<=0;owner<=0;end
        else begin
        if(state==ACTIVE)begin
            case(owner)
                0:if(!scratch.request||scratch.address!=memory.address||scratch.write!=memory.write||scratch.wmask!=memory.wmask||(scratch.write&&scratch.wdata!=memory.wdata))$fatal(1,"scratch request changed before ACK");
                1:if(!source.request||source.address!=memory.address||source.write!=memory.write||source.wmask!=memory.wmask||(source.write&&source.wdata!=memory.wdata))$fatal(1,"source request changed before ACK");
                2:if(!packet.request||packet.address!=memory.address||packet.write!=memory.write||packet.wmask!=memory.wmask||(packet.write&&packet.wdata!=memory.wdata))$fatal(1,"packet request changed before ACK");
                default:$fatal(1,"invalid transport owner");
            endcase
        end
        case(state)
            FREE:if(found&&!memory.ack)begin
                owner<=choice;state<=ACTIVE;
                case(choice)
                    0:begin memory.write<=scratch.write;memory.address<=scratch.address;
                        memory.wdata<=scratch.wdata;memory.wmask<=scratch.wmask;end
                    1:begin memory.write<=source.write;memory.address<=source.address;
                        memory.wdata<=source.wdata;memory.wmask<=source.wmask;end
                    2:begin memory.write<=packet.write;memory.address<=packet.address;
                        memory.wdata<=packet.wdata;memory.wmask<=packet.wmask;end
                    default:begin end
                endcase
            end
            ACTIVE:if(memory.ack)begin state<=GAP;next_owner<=owner==2?0:owner+1'b1;end
            GAP:if(!memory.ack)state<=FREE;
            default:state<=FREE;
        endcase
        end
    end
endmodule
