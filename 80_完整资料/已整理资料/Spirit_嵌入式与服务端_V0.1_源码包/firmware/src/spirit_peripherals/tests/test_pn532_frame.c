#include <assert.h>
#include "../pn532_frame.h"
int main(void) {
    // Real-format GetFirmwareVersion response: IC32, version1.6, support7.
    uint8_t f[] = {1,0,0,0xff,6,0xfa,0xd5,3,0x32,1,6,7,0xe8,0};
    uint8_t out[64]; size_t n=sizeof(out);
    assert(spirit_pn532_parse_normal(f,sizeof(f),2,out,&n));
    assert(n==4 && out[0]==0x32 && out[3]==7);
    for (size_t len=0;len<sizeof(f);++len) { n=sizeof(out); assert(!spirit_pn532_parse_normal(f,len,2,out,&n)); }
    n=3; assert(!spirit_pn532_parse_normal(f,sizeof(f),2,out,&n));
    n=sizeof(out); assert(!spirit_pn532_parse_normal(f,sizeof(f),0x14,out,&n));
    f[12]^=1; n=sizeof(out); assert(!spirit_pn532_parse_normal(f,sizeof(f),2,out,&n)); f[12]^=1;
    f[0]=0; n=sizeof(out); assert(!spirit_pn532_parse_normal(f,sizeof(f),2,out,&n)); f[0]=1;
    f[4]=255; n=sizeof(out); assert(!spirit_pn532_parse_normal(f,sizeof(f),2,out,&n));
    assert(!spirit_pn532_parse_normal(NULL,0,2,out,&n));
    return 0;
}
