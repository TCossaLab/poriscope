# Auto-detect platform and configure compiler, file extension,
# path separators, and removal commands depending on OS.
ifeq ($(OS),Windows_NT)
    RM = del /Q
    SEP = \\
    E   = .dll
    CC  = x86_64-w64-mingw32-gcc
    RM_NULL = nul
    DETECTED_OS = Windows
else
    UNAME_S := $(shell uname -s)
    RM = rm -f
    SEP = /
    ifeq ($(UNAME_S),Darwin)
        E = .dylib
        CC = clang
    else
        E = .so
        CC = gcc
    endif
    RM_NULL = /dev/null
    DETECTED_OS = $(UNAME_S)
endif

# Directories, file extensions, flags, and libraries
O      = o
ODIR   = build$(SEP)obj
SRC    = src
INC    = lib
INCDIR = -I$(INC)
CFLAGS = -O3 -fPIC -Wall
LIBS   = -lm

# Source files and corresponding object files
_SRCS  = wavelet_filter wdenoise ebayesthresh wdenmath wavefilt wavefunc \
         wavelib wtmath cwt cwtmath hsfft real conv utils
OBJS   = $(patsubst %,$(ODIR)$(SEP)%.$(O),$(_SRCS))

# Output shared library name (default target)
OUT    = dist$(SEP)wavelet$(E)

# Phony targets (always executed)
.PHONY: all clean dll so dylib build

# Build all variants: DLL, SO, DYLIB
all: dll so dylib

# Windows DLL build rules
dll: E = .dll
dll: CC = x86_64-w64-mingw32-gcc
dll: OUT = dist$(SEP)wavelet.dll
dll: build

# Linux SO build rules
so: E = .so
so: CC = gcc
so: OUT = dist$(SEP)wavelet.so
so: build

# macOS DYLIB build rules
dylib: E = .dylib
dylib: CC = clang
dylib: OUT = dist$(SEP)wavelet.dylib
dylib: build

# General build target: cleans and builds the library
build: clean $(OUT)

# Compile object files from source files
$(ODIR)$(SEP)%.$(O): $(SRC)/%.c $(wildcard $(INC)/*.h)
	@if not exist "$(ODIR)" mkdir "$(ODIR)" 2>$(RM_NULL)
	$(CC) -c -o $@ $< $(CFLAGS) $(INCDIR)

# Link object files into final shared library
$(OUT): $(OBJS)
	@if not exist "dist" mkdir "dist" 2>$(RM_NULL)
	$(CC) -shared -o $@ $^ $(CFLAGS) $(INCDIR) $(LIBS)

# Clean up build artifacts
clean:
	-$(RM) dist$(SEP)*.dll dist$(SEP)*.so dist$(SEP)*.dylib 2>$(RM_NULL)
	-$(RM) $(ODIR)$(SEP)*.$(O) 2>$(RM_NULL)
