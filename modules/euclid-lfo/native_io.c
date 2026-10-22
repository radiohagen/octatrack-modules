/* Firmware bindings. Called only from STORE's engine-task callbacks, apart
 * from eul_io_refuse (assembly) and eul_schedule (runtime.c). */
#include "lifecycle.h"
#define EUL_PTR(a) (*(volatile uint32_t *)(uintptr_t)(a))
static uint32_t eul_io_context[1030] __attribute__((section(".data")))={0};
static uint32_t eul_lookup[78] __attribute__((section(".data")))={0};

static int io_open(const char *path,const char *mode) {
    return ((int (*)(void *,const char *,const char *,void *,unsigned))0x40016864u)
        (eul_io_context,path,mode,eul_io_context+6,4096);
}
static int io_close(void) {
    return ((int (*)(void *))0x4001677cu)(eul_io_context);
}
static unsigned missing_path(const char *path) {
    /* Buffered open returns -12 for several lookup failures. Only a missing
     * final component (-3), not a missing parent/lock/open error, is empty.
     * Match stock's card-backend lock discipline around the raw lookup.
     * Do not call a card-specific lookup while the unmounted backend is live. */
    if (EUL_PTR(0x46c8242au)!=0x4001b570u) return 0;
    if (!((int (*)(unsigned))0x400009f4u)(0x461079c0u)) return 0;
    int result=((int (*)(const char *,void *))0x4001aa70u)(path,eul_lookup);
    ((void (*)(unsigned))0x40000ab4u)(0x461079c0u);
    return result==-3;
}
unsigned eul_io_read(const char *path,uint8_t *file) {
    int opened=io_open(path,"r");
    if (opened<0) {
        if(opened==-10) return EUL_IO_BAD; /* Existing zero-length file. */
        return opened==-12 && missing_path(path) ? EUL_IO_MISSING : EUL_IO_ERROR;
    }
    unsigned size=((unsigned (*)(unsigned))(uintptr_t)EUL_PTR(0x46c8241eu))
        (eul_io_context[0]);
    if(size!=EUL_FILE_BYTES) {
        return io_close()<0 ? EUL_IO_ERROR : EUL_IO_BAD;
    }
    int read=((int (*)(void *,void *,unsigned))0x40016564u)
        (eul_io_context,file,EUL_FILE_BYTES);
    int closed=io_close();
    return read==1 && closed>=0 ? EUL_IO_OK : EUL_IO_ERROR;
}
unsigned eul_io_write(const char *path,const uint8_t *file) {
    if(io_open(path,"w")<0) return EUL_IO_ERROR;
    int written=((int (*)(void *,const void *,unsigned))0x400166b8u)
        (eul_io_context,file,EUL_FILE_BYTES);
    int closed=io_close();
    return written==1 && closed>=0 ? EUL_IO_OK : EUL_IO_ERROR;
}
unsigned eul_io_copy(const char *dst,const char *src) {
    int result=((int (*)(const char *,const char *,int))0x40016388u)(dst,src,0);
    return result<0 ? EUL_IO_ERROR : EUL_IO_OK;
}
unsigned eul_io_path(char *out,unsigned bank,const char *suffix) {
    if(bank>=16) return 0;
    const char *dir=((const char *(*)(int,int))0x40025230u)(0,0);
    if(!dir) return 0;
    unsigned n=0;
    while(n<246 && dir[n]) { out[n]=dir[n]; ++n; }
    if(n==246) return 0;
    out[n++]='/'; out[n++]='e'; out[n++]='u'; out[n++]='l'; out[n++]='f';
    out[n++]=(char)('0'+(bank+1)/10); out[n++]=(char)('0'+(bank+1)%10);
    out[n++]='.';
    unsigned i=0;
    while(i<4 && suffix[i]) out[n++]=suffix[i++];
    if(suffix[i]) return 0;
    out[n]=0;
    return 1;
}
