// excel4_compat.cpp - Excel4 / Excel4v compatibility layer for mingw builds.
//
// The xll library's vendored XLCALL.CPP implements only the Excel 12 C API
// (Excel12 / Excel12v). On MSVC the pre-2007 API (Excel4 / Excel4v) comes
// from the Excel SDK import library XLCALL32.LIB, which mingw cannot link.
// This file provides it: convert XLOPER operands to XLOPER12, call
// Excel12v, and convert the result back. The conversions follow the
// canonical implementation from the Microsoft Excel 2013 XLL SDK.
//
// Excel 4 (pre-2007) API functions are referenced by xll::traits<XLOPER>
// (used when XLL_VERSION is 4, and by some generic code paths), so they
// must exist even in an Excel 12 add-in.
//
// Copy into your project and add excel4_compat.o to the Makefile OBJS.

#include <cstdarg>
#include <cstring>
#include <new>
#include <windows.h>

#include "xll/XLCALL.H"

namespace {

// Convert an XLOPER (pre-2007) to an XLOPER12.
// Caller must free *dst with xlFree (via Excel12(xlFree, ...)) when done.
inline void xloper_to_xloper12(const XLOPER& src, XLOPER12& dst)
{
    std::memset(&dst, 0, sizeof(dst));
    dst.xltype = src.xltype & ~(xlbitXLFree | xlbitDLLFree);

    switch (dst.xltype) {
    case xltypeNum:
        dst.val.num = src.val.num;
        break;
    case xltypeStr: {
        // counted ANSI string -> counted UTF-16 string
        int len = static_cast<unsigned char>(src.val.str[0]);
        dst.val.str = new wchar_t[static_cast<size_t>(len) + 2];
        int n = MultiByteToWideChar(CP_ACP, 0, src.val.str + 1, len,
                                    dst.val.str + 1, len);
        dst.val.str[0] = static_cast<wchar_t>(n);
        dst.xltype |= xlbitXLFree;
        break;
    }
    case xltypeBool:
        dst.val.xbool = src.val.xbool;
        break;
    case xltypeErr:
        dst.val.err = src.val.err;
        break;
    case xltypeInt:
        dst.val.w = src.val.w;
        break;
    case xltypeNil:
    case xltypeMissing:
        break;
    case xltypeMulti: {
        int rows = src.val.array.rows;
        int cols = src.val.array.columns;
        dst.val.array.lparray = new XLOPER12[static_cast<size_t>(rows) * cols];
        dst.val.array.rows = rows;
        dst.val.array.columns = cols;
        for (int i = 0; i < rows * cols; ++i) {
            xloper_to_xloper12(src.val.array.lparray[i], dst.val.array.lparray[i]);
        }
        dst.xltype |= xlbitXLFree;
        break;
    }
    case xltypeSRef:
        dst.val.sref.count = src.val.sref.count;
        dst.val.sref.ref.rwFirst = src.val.sref.ref.rwFirst;
        dst.val.sref.ref.rwLast = src.val.sref.ref.rwLast;
        dst.val.sref.ref.colFirst = src.val.sref.ref.colFirst;
        dst.val.sref.ref.colLast = src.val.sref.ref.colLast;
        break;
    case xltypeRef:
        dst.val.mref.idSheet = src.val.mref.idSheet;
        dst.val.mref.lpmref = new XLMREF12[1];
        dst.val.mref.lpmref[0].count = src.val.mref.lpmref[0].count;
        for (int i = 0; i < src.val.mref.lpmref[0].count; ++i) {
            dst.val.mref.lpmref[0].reftbl[i].rwFirst = src.val.mref.lpmref[0].reftbl[i].rwFirst;
            dst.val.mref.lpmref[0].reftbl[i].rwLast = src.val.mref.lpmref[0].reftbl[i].rwLast;
            dst.val.mref.lpmref[0].reftbl[i].colFirst = src.val.mref.lpmref[0].reftbl[i].colFirst;
            dst.val.mref.lpmref[0].reftbl[i].colLast = src.val.mref.lpmref[0].reftbl[i].colLast;
        }
        dst.xltype |= xlbitXLFree;
        break;
    default:
        // Leave as xltypeNil rather than crashing on unknown types.
        dst.xltype = xltypeNil;
        break;
    }
}

// Convert an XLOPER12 to an XLOPER (pre-2007).
// Caller must free *dst with xlFree (via Excel4(xlFree, ...)) when done.
inline void xloper12_to_xloper(const XLOPER12& src, XLOPER& dst)
{
    std::memset(&dst, 0, sizeof(dst));
    dst.xltype = static_cast<WORD>(src.xltype & ~(xlbitXLFree | xlbitDLLFree));

    switch (dst.xltype) {
    case xltypeNum:
        dst.val.num = src.val.num;
        break;
    case xltypeStr: {
        // counted UTF-16 string -> counted ANSI string
        int len = src.val.str[0];
        dst.val.str = new char[static_cast<size_t>(len) + 2];
        int n = WideCharToMultiByte(CP_ACP, 0, src.val.str + 1, len,
                                    dst.val.str + 1, len, nullptr, nullptr);
        dst.val.str[0] = static_cast<char>(n);
        dst.xltype |= xlbitXLFree;
        break;
    }
    case xltypeBool:
        dst.val.xbool = src.val.xbool;
        break;
    case xltypeErr:
        dst.val.err = static_cast<int>(src.val.err);
        break;
    case xltypeInt:
        dst.val.w = src.val.w;
        break;
    case xltypeNil:
    case xltypeMissing:
        break;
    case xltypeMulti: {
        int rows = src.val.array.rows;
        int cols = src.val.array.columns;
        dst.val.array.lparray = new XLOPER[static_cast<size_t>(rows) * cols];
        dst.val.array.rows = rows;
        dst.val.array.columns = cols;
        for (int i = 0; i < rows * cols; ++i) {
            xloper12_to_xloper(src.val.array.lparray[i], dst.val.array.lparray[i]);
        }
        dst.xltype |= xlbitXLFree;
        break;
    }
    case xltypeSRef:
        dst.val.sref.count = src.val.sref.count;
        dst.val.sref.ref.rwFirst = src.val.sref.ref.rwFirst;
        dst.val.sref.ref.rwLast = src.val.sref.ref.rwLast;
        dst.val.sref.ref.colFirst = src.val.sref.ref.colFirst;
        dst.val.sref.ref.colLast = src.val.sref.ref.colLast;
        break;
    case xltypeRef:
        dst.val.mref.idSheet = src.val.mref.idSheet;
        dst.val.mref.lpmref = new XLMREF[1];
        dst.val.mref.lpmref[0].count = static_cast<WORD>(src.val.mref.lpmref[0].count);
        for (int i = 0; i < src.val.mref.lpmref[0].count; ++i) {
            dst.val.mref.lpmref[0].reftbl[i].rwFirst = src.val.mref.lpmref[0].reftbl[i].rwFirst;
            dst.val.mref.lpmref[0].reftbl[i].rwLast = src.val.mref.lpmref[0].reftbl[i].rwLast;
            dst.val.mref.lpmref[0].reftbl[i].colFirst = src.val.mref.lpmref[0].reftbl[i].colFirst;
            dst.val.mref.lpmref[0].reftbl[i].colLast = src.val.mref.lpmref[0].reftbl[i].colLast;
        }
        dst.xltype |= xlbitXLFree;
        break;
    default:
        dst.xltype = xltypeNil;
        break;
    }
}

} // namespace

extern "C" int pascal Excel4v(int xlfn, LPXLOPER operRes, int count, LPXLOPER opers[])
{
    if (count < 0 || count > 255) {
        return xlretFailed;
    }

    XLOPER12 res12 = { .xltype = xltypeNil };
    XLOPER12* args12[255] = { nullptr };

    for (int i = 0; i < count; ++i) {
        args12[i] = new XLOPER12;
        xloper_to_xloper12(*opers[i], *args12[i]);
    }

    int result = Excel12v(xlfn, &res12, count, args12);

    if (operRes) {
        xloper12_to_xloper(res12, *operRes);
    }

    // release the converted arguments; free any Excel-allocated members
    for (int i = 0; i < count; ++i) {
        if (args12[i]->xltype & xlbitXLFree) {
            Excel12(xlFree, nullptr, 1, &args12[i]);
        }
        delete args12[i];
    }
    if (res12.xltype & xlbitXLFree) {
        Excel12(xlFree, nullptr, 1, &res12);
    }

    return result;
}

extern "C" int _cdecl Excel4(int xlfn, LPXLOPER operRes, int count, ...)
{
    if (count < 0 || count > 255) {
        return xlretFailed;
    }

    va_list ap;
    va_start(ap, count);
    XLOPER* opers[255];
    for (int i = 0; i < count; ++i) {
        opers[i] = va_arg(ap, LPXLOPER);
    }
    va_end(ap);

    return Excel4v(xlfn, operRes, count, opers);
}
