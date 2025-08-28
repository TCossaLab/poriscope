# wavelet DLL cross-platform Makefile
#
# This Makefile builds a shared library for the wavelet library across:
# - Windows (.dll)
# - Linux (.so)
# - macOS (.dylib)
#
# It supports native builds and cross-compilation with mingw-w64 on Linux.
# To force Windows cross-build on Linux: `make dll CROSS=true`
# To build all: `make dll so dylib`

# Detect cross-compilation
ifeq ($(CROSS),true)
    CC     = x86_64-w64-mingw32-gcc
    E      = .dll
    RM     = rm -f
    MKDIR  = mkdir -p
    RMDIR  = rm -rf
    SEP    = /
else
    ifeq ($(OS),Windows_NT)
        CC     = x86_64-w64-mingw32-gcc
        E      = .dll
        RM     = del /F /Q
        MKDIR  = if not exist
        RMDIR  = rmdir /S /Q
        SEP    = \\
    else
        UNAME_S := $(shell uname -s)
        ifeq ($(UNAME_S),Darwin)
            CC     = clang
            E      = .dylib
        else
            CC     = gcc
            E      = .so
        endif
        RM     = rm -f
        MKDIR  = mkdir -p
        RMDIR  = rm -rf
        SEP    = /
    endif
endif

# Output and object settings
O       = o
ODIR    = build/obj
SRC     = src
INC     = lib
INCDIR  = -I$(INC)
DEPS    = $(wildcard $(INC)/*.h)

# C compiler flags and libraries
CFLAGS  = -O3 -D_GNU_SOURCE -fPIC -Wall
LIBS    = -lm

# Source files
_SRCS   = wavelet_filter wdenoise ebayesthresh wdenmath wavefilt wavefunc \
          wavelib wtmath cwt cwtmath hsfft real conv utils
OBJS    = $(patsubst %,$(ODIR)$(SEP)%.$(O),$(_SRCS))

# Platform-specific outputs
DLL_OUT   = dist$(SEP)wavelet.dll
SO_OUT    = dist$(SEP)wavelet.so
DYLIB_OUT = dist$(SEP)wavelet.dylib

# Default output determined by platform
OUT ?= dist$(SEP)wavelet$(E)

.PHONY: all clean dll so dylib

# Default target: build platform-specific shared library
all: $(OUT)

# Platform-specific targets
dll:
	@$(MKDIR) dist
	$(MAKE) OUT=$(DLL_OUT) E=.dll CC=x86_64-w64-mingw32-gcc

so:
	@$(MKDIR) dist
	$(MAKE) OUT=$(SO_OUT) E=.so CC=gcc

dylib:
	@$(MKDIR) dist
	$(MAKE) OUT=$(DYLIB_OUT) E=.dylib CC=clang

# Compile each .c to .o
$(ODIR)$(SEP)%.$(O): $(SRC)/%.c $(DEPS)
	@$(MKDIR) $(ODIR)
	$(CC) -c -o $@ $< $(CFLAGS) $(INCDIR)

# Link all .o files into platform-specific shared library
$(DLL_OUT) $(SO_OUT) $(DYLIB_OUT): $(OBJS)
	@$(MKDIR) dist
	$(CC) -shared -o $@ $^ $(CFLAGS) $(INCDIR) $(LIBS)

# Remove all build outputs
clean:
	-$(RM) dist$(SEP)*.dll dist$(SEP)*.so dist$(SEP)*.dylib
	-$(RM) $(ODIR)$(SEP)*.$(O)
