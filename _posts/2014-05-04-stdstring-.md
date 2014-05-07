---
layout: post
title: "std::string 和引用计数"
description: ""
category: C++
tags: [C++, STL, code reading]
---
{% include JB/setup %}
std::string 又是 STL 中最最最最最最最常用的没有之一的设施。正因为简单，不大被关注。
初用 C++ 的人一定不知道他是从 basic\_string 特化出来的，对 C++ 有一定了解的人可能也不知道 string 里面是带引用计数的。现在就来详细剖析一下 string 或者说 basic\_string 吧

include/std/string 里面是一堆的 include，就不贴出来浪费篇幅了，有关的是 stringfwd.h，basic\_string.h, basic\_string.tcc 三个文件。

stringfwd.h
{% highlight cpp %}
  template<class _CharT>
    struct char_traits;
  template<typename _CharT, typename _Traits = char_traits<_CharT>,
           typename _Alloc = allocator<_CharT> >
    class basic_string;
  template<> struct char_traits<char>;
  /// A string of @c char
  typedef basic_string<char> string;
#ifdef _GLIBCXX_USE_WCHAR_T
  template<> struct char_traits<wchar_t>;
  /// A string of @c wchar_t
  typedef basic_string<wchar_t> wstring;
#endif
#if ((__cplusplus >= 201103L) \
     && defined(_GLIBCXX_USE_C99_STDINT_TR1))
  template<> struct char_traits<char16_t>;
  template<> struct char_traits<char32_t>;
  /// A string of @c char16_t
  typedef basic_string<char16_t> u16string;
  /// A string of @c char32_t
  typedef basic_string<char32_t> u32string;
{% endhighlight %}

<!--more-->
模板的各种特化，注意到 string 也是带 allocator 的，还有 char\_traits 结构（在 char\_traits.h）。

来看 basic\_string.h

{% highlight cpp %}
  template<typename _CharT, typename _Traits, typename _Alloc>
    class basic_string
    {
      typedef typename _Alloc::template rebind<_CharT>::other _CharT_alloc_type;
      // Types:
    public:
      typedef _Traits traits_type;
      typedef typename _Traits::char_type value_type;
      typedef _Alloc allocator_type;
      typedef typename _CharT_alloc_type::size_type size_type;
      typedef typename _CharT_alloc_type::difference_type difference_type;
      typedef typename _CharT_alloc_type::reference reference;
      typedef typename _CharT_alloc_type::const_reference const_reference;
      typedef typename _CharT_alloc_type::pointer pointer;
      typedef typename _CharT_alloc_type::const_pointer const_pointer;
      typedef __gnu_cxx::__normal_iterator<pointer, basic_string> iterator;
      typedef __gnu_cxx::__normal_iterator<const_pointer, basic_string>
                                                            const_iterator;
      typedef std::reverse_iterator<const_iterator> const_reverse_iterator;
      typedef std::reverse_iterator<iterator> reverse_iterator;
{% endhighlight %}

跟 vector 的开头差不多。

关键来了。
{% highlight cpp %}
    private:
      // _Rep: string representation
      // Invariants:
      // 1. String really contains _M_length + 1 characters: due to 21.3.4
      // must be kept null-terminated.
      // 2. _M_capacity >= _M_length
      // Allocated memory is always (_M_capacity + 1) * sizeof(_CharT).
      // 3. _M_refcount has three states:
      // -1: leaked, one reference, no ref-copies allowed, non-const.
      // 0: one reference, non-const.
      // n>0: n + 1 references, operations require a lock, const.
      // 4. All fields==0 is an empty string, given the extra storage
      // beyond-the-end for a null terminator; thus, the shared
      // empty string representation needs no constructor.
      struct _Rep_base
      {
        size_type _M_length;
        size_type _M_capacity;
        _Atomic_word _M_refcount;
      };

      struct _Rep : _Rep_base

{% endhighlight %}

注意到 string 也是有 capacity 和 length 的，那它是和 vector 一样每次 x2 么？\_Rep\_base 中的 \_M\_refcount 三种状态， -1 是 leaked（为什么酱紫?），0 是 1 个引用，n 是 n + 1 个引用，需要原子操作。

后面是 \_Rep，成员很多，暂时跳过直接看 basic\_string，然后根据需要回来看 \_Rep。

basic\_string 只有两个  data member
{% highlight cpp %}
      // Data Members (public):
      // NB: This is an unsigned type, and thus represents the maximum
      // size that the allocator can hold.
      /// Value returned by various member functions when they fail.
      static const size_type npos = static_cast<size_type>(-1);
    private:
      // Data Members (private):
      mutable _Alloc_hider _M_dataplus;
{% endhighlight %}

不大对头的样子，\_Rep 呢？

{% highlight cpp %}
      // Use empty-base optimization: http://www.cantrip.org/emptyopt.html
      struct _Alloc_hider : _Alloc
      {
        _Alloc_hider(_CharT* __dat, const _Alloc& __a) _GLIBCXX_NOEXCEPT
        : _Alloc(__a), _M_p(__dat) { }
        _CharT* _M_p; // The actual data.
      };
{% endhighlight %}

不不，不在 \_Alloc 里面，那只能在 \_M\_p 上

{% highlight cpp %}
      _CharT*
      _M_data() const _GLIBCXX_NOEXCEPT
      { return _M_dataplus._M_p; }
      _CharT*
      _M_data(_CharT* __p) _GLIBCXX_NOEXCEPT
      { return (_M_dataplus._M_p = __p); }
      _Rep*
      _M_rep() const _GLIBCXX_NOEXCEPT
      { return &((reinterpret_cast<_Rep*> (_M_data()))[-1]); }
{% endhighlight %}

这个变态。。 为什么不直接把 \_M\_p 声明成 \_Rep* ，而是要做 cast，而且还是取 -1 index。有必要去看内存分配的情况。那就从构造开始~

{% highlight cpp %}
      basic_string()
#if _GLIBCXX_FULLY_DYNAMIC_STRING == 0
      : _M_dataplus(_S_empty_rep()._M_refdata(), _Alloc()) { }
#else
      : _M_dataplus(_S_construct(size_type(), _CharT(), _Alloc()), _Alloc()){ }
#endif
{% endhighlight %}

{% highlight cpp %}
      static _Rep&
      _S_empty_rep() _GLIBCXX_NOEXCEPT
      { return _Rep::_S_empty_rep(); }
{% endhighlight %}

在 \_Rep 里面
{% highlight cpp %}
        // The following storage is init'd to 0 by the linker, resulting
        // (carefully) in an empty string with one reference.
        static size_type _S_empty_rep_storage[];
        static _Rep&
        _S_empty_rep() _GLIBCXX_NOEXCEPT
        {
          // NB: Mild hack to avoid strict-aliasing warnings. Note that
          // _S_empty_rep_storage is never modified and the punning should
          // be reasonably safe in this case.
          void* __p = reinterpret_cast<void*>(&_S_empty_rep_storage);
          return *reinterpret_cast<_Rep*>(__p);
        }
{% endhighlight %}

把他强制 cast 成了 \_Rep\*，专门在 static 上给了一块 storage，为什么这么做呢？ 看一下 storage 分配了多大？

{% highlight cpp %}
  // Linker sets _S_empty_rep_storage to all 0s (one reference, empty string)
  // at static init time (before static ctors are run).
  template<typename _CharT, typename _Traits, typename _Alloc>
    typename basic_string<_CharT, _Traits, _Alloc>::size_type
    basic_string<_CharT, _Traits, _Alloc>::_Rep::_S_empty_rep_storage[
    (sizeof(_Rep_base) + sizeof(_CharT) + sizeof(size_type) - 1) /
      sizeof(size_type)];
{% endhighlight %}

\_Rep 并没有 data member，也没虚表啥的，所以 sizeof(\_Rep\_base) 就是 sizeof(\_Rep)，后面的 sizeof(size\_type) - 1 是为了除 sizeof(size\_type) 的时候有余数进 1，除以 sizeof(size\_type) 是为了适应 \_S\_empty\_rep\_storage 本身的 type（要一个同样大小的数组么）。那为什么要加 sizeof(\_CharT)？ '\0' 喔。

为了适应 empty string 有 '\0'，搞了一个 size\_type 的数组。

如果 string 是 fully dynamic 呢？ 则会直接去上 \_S\_construct。

{% highlight cpp %}
  template<typename _CharT, typename _Traits, typename _Alloc>
    template<typename _InIterator>
      _CharT*
      basic_string<_CharT, _Traits, _Alloc>::
      _S_construct(_InIterator __beg, _InIterator __end, const _Alloc& __a,
                   input_iterator_tag)

  template<typename _CharT, typename _Traits, typename _Alloc>
    template <typename _InIterator>
      _CharT*
      basic_string<_CharT, _Traits, _Alloc>::
      _S_construct(_InIterator __beg, _InIterator __end, const _Alloc& __a,
                   forward_iterator_tag)

  template<typename _CharT, typename _Traits, typename _Alloc>
    _CharT*
    basic_string<_CharT, _Traits, _Alloc>::
    _S_construct(size_type __n, _CharT __c, const _Alloc& __a)
{% endhighlight %}

跟 vector 的 \_S\_construct 感觉好像。现在调的是最后一个。

{% highlight cpp %}
    {
#if _GLIBCXX_FULLY_DYNAMIC_STRING == 0
      if (__n == 0 && __a == _Alloc())
        return _S_empty_rep()._M_refdata();
#endif
      // Check for out_of_range and length_error exceptions.
      _Rep* __r = _Rep::_S_create(__n, size_type(0), __a);
      if (__n)
        _M_assign(__r->_M_refdata(), __n, __c);
      __r->_M_set_length_and_sharable(__n);
      return __r->_M_refdata();
    }
{% endhighlight %}

来看 \_S\_create
{% highlight cpp %}
  template<typename _CharT, typename _Traits, typename _Alloc>
    typename basic_string<_CharT, _Traits, _Alloc>::_Rep*
    basic_string<_CharT, _Traits, _Alloc>::_Rep::
    _S_create(size_type __capacity, size_type __old_capacity,
              const _Alloc& __alloc)
    {
      // _GLIBCXX_RESOLVE_LIB_DEFECTS
      // 83. String::npos vs. string::max_size()
      if (__capacity > _S_max_size)
        __throw_length_error(__N("basic_string::_S_create"));
{% endhighlight %}

噗，不过我觉得还是用 max\_size 把来表示最大 size。看一下 \_S\_max\_size 

{% highlight cpp %}
      /// Returns the size() of the largest possible %string.
      size_type
      max_size() const _GLIBCXX_NOEXCEPT
      { return _Rep::_S_max_size; }

  template<typename _CharT, typename _Traits, typename _Alloc>
    const typename basic_string<_CharT, _Traits, _Alloc>::size_type
    basic_string<_CharT, _Traits, _Alloc>::
    _Rep::_S_max_size = (((npos - sizeof(_Rep_base))/sizeof(_CharT)) - 1) / 4;
{% endhighlight %}

npos 是 sizeof(size\_type)，减去 \_Rep\_base 占用的空间，除以 sizeof(\_CharT) 是允许的字符长度，减去一个 terminator。为什么除 4？ gcc 你就这么抠么？来看一下 libcxx 的

{% highlight cpp %}
template <class _CharT, class _Traits, class _Allocator>
inline _LIBCPP_INLINE_VISIBILITY
typename basic_string<_CharT, _Traits, _Allocator>::size_type
basic_string<_CharT, _Traits, _Allocator>::max_size() const _NOEXCEPT
{
    size_type __m = __alloc_traits::max_size(__alloc());
#if _LIBCPP_BIG_ENDIAN
    return (__m <= ~__long_mask ? __m : __m/2) - __alignment;
#else
    return __m - __alignment;
#endif
}
{% endhighlight %}

\_\_alignment 是之前定义的常数 16 。。。。 反正这个除 4 没什么道理。顺便吐槽一句，libcxx 里面 basic\_string 写那一坨真是不堪直视。。。。

回来继续 \_S\_create，变态的部分来了。

{% highlight cpp %}
      const size_type __pagesize = 4096;
      const size_type __malloc_header_size = 4 * sizeof(void*);
{% endhighlight %}

竟然对 pagesize 和 malloc\_header\_size 做了估计。。。 看来要做很奇怪的优化，vector 都没做的这么厚道好么

{% highlight cpp %}
      if (__capacity > __old_capacity && __capacity < 2 * __old_capacity)
        __capacity = 2 * __old_capacity;
{% endhighlight %}

如果可以的话，就做 x2.

{% highlight cpp %}
      // NB: Need an array of char_type[__capacity], plus a terminating
      // null char_type() element, plus enough for the _Rep data structure.
      // Whew. Seemingly so needy, yet so elemental.
      size_type __size = (__capacity + 1) * sizeof(_CharT) + sizeof(_Rep);
      const size_type __adj_size = __size + __malloc_header_size;
      if (__adj_size > __pagesize && __capacity > __old_capacity)
        {
          const size_type __extra = __pagesize - __adj_size % __pagesize;
          __capacity += __extra / sizeof(_CharT);
          // Never allocate a string bigger than _S_max_size.
          if (__capacity > _S_max_size)
            __capacity = _S_max_size;
          __size = (__capacity + 1) * sizeof(_CharT) + sizeof(_Rep);
        }
{% endhighlight %}

如果超越了 \_\_pagesize，会把 page 后面的补上。。。当然不可以超过 \_S\_max\_size。 omg，4K 的 string 平时谁都不会用到吧，网络通信的时候应该会~。

{% highlight cpp %}
      // NB: Might throw, but no worries about a leak, mate: _Rep()
      // does not throw.
      void* __place = _Raw_bytes_alloc(__alloc).allocate(__size);
      _Rep *__p = new (__place) _Rep;
      __p->_M_capacity = __capacity;
      // ABI compatibility - 3.4.x set in _S_create both
      // _M_refcount and _M_length. All callers of _S_create
      // in basic_string.tcc then set just _M_length.
      // In 4.0.x and later both _M_refcount and _M_length
      // are initialized in the callers, unfortunately we can
      // have 3.4.x compiled code with _S_create callers inlined
      // calling 4.0.x+ _S_create.
      __p->_M_set_sharable();
      return __p;
{% endhighlight %}

abi compability 有变化，不过跟我们无关~ 来看后面 \_M\_set\_sharable

{% highlight cpp %}
        void
        _M_set_sharable() _GLIBCXX_NOEXCEPT
        { this->_M_refcount = 0; }
{% endhighlight %}

就是 ref count 设成了 0。

最基本的构造搞定了，来看 copy ctor，这应该是引用计数使用的地方

{% highlight cpp %}
  template<typename _CharT, typename _Traits, typename _Alloc>
    basic_string<_CharT, _Traits, _Alloc>::
    basic_string(const basic_string& __str)
    : _M_dataplus(__str._M_rep()->_M_grab(_Alloc(__str.get_allocator()),
                                          __str.get_allocator()),
                  __str.get_allocator())
    { }
{% endhighlight %}

调用了 \_Rep 的 \_M\_grab。

{% highlight cpp %}
        _CharT*
        _M_grab(const _Alloc& __alloc1, const _Alloc& __alloc2)
        {
          return (!_M_is_leaked() && __alloc1 == __alloc2)
                  ? _M_refcopy() : _M_clone(__alloc1);
        }
{% endhighlight %}

如果 refcount 不是 -1 且 allocator 相同，那么就可以 refcopy

{% highlight cpp %}
        _CharT*
        _M_refcopy() throw()
        {
#if _GLIBCXX_FULLY_DYNAMIC_STRING == 0
          if (__builtin_expect(this != &_S_empty_rep(), false))
#endif
            __gnu_cxx::__atomic_add_dispatch(&this->_M_refcount, 1);
          return _M_refdata();
        } // XXX MT
{% endhighlight %}

\_\_buildin\_expect，对分支预测的优化。 atomic\_add 和之前 shared\_ptr 里面的同理，增加引用计数。

{% highlight cpp %}
        _CharT*
        _M_refdata() throw()
        { return reinterpret_cast<_CharT*>(this + 1); }
{% endhighlight %}

这个 cast 做的略神奇，\_Rep 和 char 都分配在 \_M\_dataplus 那个指针的那块内存上，\_Rep 后面就是 char。。。总之，这么写感觉不太好。

如果是 \_M\_clone 呢？

{% highlight cpp %}
  template<typename _CharT, typename _Traits, typename _Alloc>
    _CharT*
    basic_string<_CharT, _Traits, _Alloc>::_Rep::
    _M_clone(const _Alloc& __alloc, size_type __res)
    {
      // Requested capacity of the clone.
      const size_type __requested_cap = this->_M_length + __res;
      _Rep* __r = _Rep::_S_create(__requested_cap, this->_M_capacity,
                                  __alloc);
      if (this->_M_length)
        _M_copy(__r->_M_refdata(), _M_refdata(), this->_M_length);
      __r->_M_set_length_and_sharable(this->_M_length);
      return __r->_M_refdata();
    }
{% endhighlight %}

分配之后做 copy。这里调用的 trait 的 copy 和 assgin，里面坐了一些 trait 匹配，对不同类型做了优化。
{% highlight cpp %}
      // When __n = 1 way faster than the general multichar
      // traits_type::copy/move/assign.
      static void
      _M_copy(_CharT* __d, const _CharT* __s, size_type __n) _GLIBCXX_NOEXCEPT
      {
        if (__n == 1)
          traits_type::assign(*__d, *__s);
        else
          traits_type::copy(__d, __s, __n);
      }
{% endhighlight %}

然后再 set length 和 sharable

{% highlight cpp %}
        void
        _M_set_length_and_sharable(size_type __n) _GLIBCXX_NOEXCEPT
        {
#if _GLIBCXX_FULLY_DYNAMIC_STRING == 0
          if (__builtin_expect(this != &_S_empty_rep(), false))
#endif
            {
              this->_M_set_sharable(); // One reference.
              this->_M_length = __n;
              traits_type::assign(this->_M_refdata()[__n], _S_terminal);
              // grrr. (per 21.3.4)
              // You cannot leave those LWG people alone for a second.
            }
        }
{% endhighlight %}

注意 termial 是不做 copy 的，最后才 assign 一个 \_S\_terminal 。

其他的 ctor 也都是通过 \_S\_construct，都是转化成 input\_iterator 和 forward\_iterator 两种。

{% highlight cpp %}
  template<typename _CharT, typename _Traits, typename _Alloc>
    basic_string<_CharT, _Traits, _Alloc>::
    basic_string(const basic_string& __str, size_type __pos, size_type __n)
    : _M_dataplus(_S_construct(__str._M_data()
                               + __str._M_check(__pos,
                                                "basic_string::basic_string"),
                               __str._M_data() + __str._M_limit(__pos, __n)
                               + __pos, _Alloc()), _Alloc())

  template<typename _CharT, typename _Traits, typename _Alloc>
    basic_string<_CharT, _Traits, _Alloc>::
    basic_string(const basic_string& __str, size_type __pos,
                 size_type __n, const _Alloc& __a)
    : _M_dataplus(_S_construct(__str._M_data()
                               + __str._M_check(__pos,
                                                "basic_string::basic_string"),
                               __str._M_data() + __str._M_limit(__pos, __n)
                               + __pos, __a), __a)
    { }
  // TBD: DPG annotate
  template<typename _CharT, typename _Traits, typename _Alloc>
    basic_string<_CharT, _Traits, _Alloc>::
    basic_string(const _CharT* __s, size_type __n, const _Alloc& __a)
    : _M_dataplus(_S_construct(__s, __s + __n, __a), __a)
    { }
  // TBD: DPG annotate
  template<typename _CharT, typename _Traits, typename _Alloc>
    basic_string<_CharT, _Traits, _Alloc>::
    basic_string(const _CharT* __s, const _Alloc& __a)
    : _M_dataplus(_S_construct(__s, __s ? __s + traits_type::length(__s) :
                               __s + npos, __a), __a)
    { }
  template<typename _CharT, typename _Traits, typename _Alloc>
    basic_string<_CharT, _Traits, _Alloc>::
    basic_string(size_type __n, _CharT __c, const _Alloc& __a)
    : _M_dataplus(_S_construct(__n, __c, __a), __a)
    { }

  // TBD: DPG annotate
  template<typename _CharT, typename _Traits, typename _Alloc>
    template<typename _InputIterator>
    basic_string<_CharT, _Traits, _Alloc>::
    basic_string(_InputIterator __beg, _InputIterator __end, const _Alloc& __a)
    : _M_dataplus(_S_construct(__beg, __end, __a), __a)
    { }
#if __cplusplus >= 201103L
  template<typename _CharT, typename _Traits, typename _Alloc>
    basic_string<_CharT, _Traits, _Alloc>::
    basic_string(initializer_list<_CharT> __l, const _Alloc& __a)
    : _M_dataplus(_S_construct(__l.begin(), __l.end(), __a), __a)
    { }
#endif
{% endhighlight %}

顺便还做了 range check

{% highlight cpp %}
      size_type
      _M_check(size_type __pos, const char* __s) const
      {
        if (__pos > this->size())
          __throw_out_of_range_fmt(__N("%s: __pos (which is %zu) > "
                                       "this->size() (which is %zu)"),
                                   __s, __pos, this->size());
        return __pos;
      }
{% endhighlight %}

foward\_iterator 做 construct 的过程跟之前的差不多，因为 begin 和 end 确定，只要分配好内存，copy 过去就好了。
注意要处理 begin 是 null 的情况。

{% highlight cpp %}
  template<typename _CharT, typename _Traits, typename _Alloc>
    template <typename _InIterator>
      _CharT*
      basic_string<_CharT, _Traits, _Alloc>::
      _S_construct(_InIterator __beg, _InIterator __end, const _Alloc& __a,
                   forward_iterator_tag)
      {
#if _GLIBCXX_FULLY_DYNAMIC_STRING == 0
        if (__beg == __end && __a == _Alloc())
          return _S_empty_rep()._M_refdata();
#endif
        // NB: Not required, but considered best practice.
        if (__gnu_cxx::__is_null_pointer(__beg) && __beg != __end)
          __throw_logic_error(__N("basic_string::_S_construct null not valid"));
        const size_type __dnew = static_cast<size_type>(std::distance(__beg,
                                                                      __end));
        // Check for out_of_range and length_error exceptions.
        _Rep* __r = _Rep::_S_create(__dnew, size_type(0), __a);
        __try
          { _S_copy_chars(__r->_M_refdata(), __beg, __end); }
        __catch(...)
          {
            __r->_M_destroy(__a);
            __throw_exception_again;
          }
        __r->_M_set_length_and_sharable(__dnew);
        return __r->_M_refdata();
      }
{% endhighlight %}

另外 copy 是调用 \_S\_copy\_chars ，因为这里并不知道 iterator 是怎样的，不过某些情况可以做优化~~

{% highlight cpp %}
      template<class _Iterator>
        static void
        _S_copy_chars(_CharT* __p, _Iterator __k1, _Iterator __k2)
        _GLIBCXX_NOEXCEPT
        {
          for (; __k1 != __k2; ++__k1, ++__p)
            traits_type::assign(*__p, *__k1); // These types are off.
        }
      static void
      _S_copy_chars(_CharT* __p, iterator __k1, iterator __k2) _GLIBCXX_NOEXCEPT
      { _S_copy_chars(__p, __k1.base(), __k2.base()); }
      static void
      _S_copy_chars(_CharT* __p, const_iterator __k1, const_iterator __k2)
      _GLIBCXX_NOEXCEPT
      { _S_copy_chars(__p, __k1.base(), __k2.base()); }
      static void
      _S_copy_chars(_CharT* __p, _CharT* __k1, _CharT* __k2) _GLIBCXX_NOEXCEPT
      { _M_copy(__p, __k1, __k2 - __k1); }
      static void
      _S_copy_chars(_CharT* __p, const _CharT* __k1, const _CharT* __k2)
      _GLIBCXX_NOEXCEPT
      { _M_copy(__p, __k1, __k2 - __k1); }
{% endhighlight %}

对于 input\_iterator 来说，只能苦逼的一个一个来做，不过这里还是做了个小优化，先分配了 128 的 buffer

{% highlight cpp %}
  template<typename _CharT, typename _Traits, typename _Alloc>
    template<typename _InIterator>
      _CharT*
      basic_string<_CharT, _Traits, _Alloc>::
      _S_construct(_InIterator __beg, _InIterator __end, const _Alloc& __a,
                   input_iterator_tag)
      {
#if _GLIBCXX_FULLY_DYNAMIC_STRING == 0
        if (__beg == __end && __a == _Alloc())
          return _S_empty_rep()._M_refdata();
#endif
        // Avoid reallocation for common case.
        _CharT __buf[128];
        size_type __len = 0;
        while (__beg != __end && __len < sizeof(__buf) / sizeof(_CharT))
          {
            __buf[__len++] = *__beg;
            ++__beg;
          }
{% endhighlight %}

如果 buffer 都撑不住了。。。那就老实分配，copy 过去然后接着接受吧。

{% highlight cpp %}
        _Rep* __r = _Rep::_S_create(__len, size_type(0), __a);
        _M_copy(__r->_M_refdata(), __buf, __len);
        __try
          {
            while (__beg != __end)
              {
                if (__len == __r->_M_capacity)
                  {
                    // Allocate more space.
                    _Rep* __another = _Rep::_S_create(__len + 1, __len, __a);
                    _M_copy(__another->_M_refdata(), __r->_M_refdata(), __len);
                    __r->_M_destroy(__a);
                    __r = __another;
                  }
                __r->_M_refdata()[__len++] = *__beg;
                ++__beg;
              }
          }
        __catch(...)
          {
            __r->_M_destroy(__a);
            __throw_exception_again;
          }
        __r->_M_set_length_and_sharable(__len);
        return __r->_M_refdata();
      }
{% endhighlight %}

当然做 copy 之后，之前分配的要 \_M\_destroy。

{% highlight cpp %}
  template<typename _CharT, typename _Traits, typename _Alloc>
    void
    basic_string<_CharT, _Traits, _Alloc>::_Rep::
    _M_destroy(const _Alloc& __a) throw ()
    {
      const size_type __size = sizeof(_Rep_base) +
                               (this->_M_capacity + 1) * sizeof(_CharT);
      _Raw_bytes_alloc(__a).deallocate(reinterpret_cast<char*>(this), __size);
    }
{% endhighlight %}

构造基本就这样，析构呢？

{% highlight cpp %}
      ~basic_string() _GLIBCXX_NOEXCEPT
      { _M_rep()->_M_dispose(this->get_allocator()); }
{% endhighlight %}

dispose 的过程可以联想 shared\_pr 的 \_M\_refcount。

{% highlight cpp %}
        void
        _M_dispose(const _Alloc& __a) _GLIBCXX_NOEXCEPT
        {
#if _GLIBCXX_FULLY_DYNAMIC_STRING == 0
          if (__builtin_expect(this != &_S_empty_rep(), false))
#endif
            {
              // Be race-detector-friendly. For more info see bits/c++config.
              _GLIBCXX_SYNCHRONIZATION_HAPPENS_BEFORE(&this->_M_refcount);
              if (__gnu_cxx::__exchange_and_add_dispatch(&this->_M_refcount,
                                                         -1) <= 0)
                {
                  _GLIBCXX_SYNCHRONIZATION_HAPPENS_AFTER(&this->_M_refcount);
                  _M_destroy(__a);
                }
            }
        } // XXX MT
{% endhighlight %}

注意，这里 refcount == -1才是没别人用了。。

operator=(&) 等基本都被托管到了 assign 上。

{% highlight cpp %}
      basic_string&
      operator=(const basic_string& __str)
      { return this->assign(__str); }

      basic_string&
      operator=(const _CharT* __s)
      { return this->assign(__s); }

      basic_string&
      operator=(_CharT __c)
      {
        this->assign(1, __c);
        return *this;
      }

      basic_string&
      operator=(initializer_list<_CharT> __l)
      {
        this->assign(__l.begin(), __l.size());
        return *this;
      }
{% endhighlight %}

遇到右值则直接 swap

{% highlight cpp %}
      basic_string&
      operator=(basic_string&& __str)
      {
        // NB: DR 1204.
        this->swap(__str);
        return *this;
      }
{% endhighlight %}

酱紫的话，去看 assign 好了。

{% highlight cpp %}
  template<typename _CharT, typename _Traits, typename _Alloc>
    basic_string<_CharT, _Traits, _Alloc>&
    basic_string<_CharT, _Traits, _Alloc>::
    assign(const basic_string& __str)
    {
      if (_M_rep() != __str._M_rep())
        {
          // XXX MT
          const allocator_type __a = this->get_allocator();
          _CharT* __tmp = __str._M_rep()->_M_grab(__a, __str.get_allocator());
          _M_rep()->_M_dispose(__a);
          _M_data(__tmp);
        }
      return *this;
    }
{% endhighlight %}

如果不是一个 \_Rep 的话，就 grab 人家的 \_Rep，然后 dispose 掉自己的。

{% highlight cpp %}
      basic_string&
      assign(const basic_string& __str, size_type __pos, size_type __n)
      { return this->assign(__str._M_data()
                            + __str._M_check(__pos, "basic_string::assign"),
                            __str._M_limit(__pos, __n)); }

      basic_string&
      assign(const _CharT* __s, size_type __n);

      basic_string&
      assign(const _CharT* __s)
      {
        __glibcxx_requires_string(__s);
        return this->assign(__s, traits_type::length(__s));
      }
{% endhighlight %}

这几种都属于  assign(const \_CharT* \_\_s, size\_type \_\_n);，

{% highlight cpp %}
  template<typename _CharT, typename _Traits, typename _Alloc>
    basic_string<_CharT, _Traits, _Alloc>&
    basic_string<_CharT, _Traits, _Alloc>::
    assign(const _CharT* __s, size_type __n)
    {
      __glibcxx_requires_string_len(__s, __n);
      _M_check_length(this->size(), __n, "basic_string::assign");
      if (_M_disjunct(__s) || _M_rep()->_M_is_shared())
        return _M_replace_safe(size_type(0), this->size(), __s, __n);
      else
        {
          // Work in-place.
          const size_type __pos = __s - _M_data();
          if (__pos >= __n)
            _M_copy(_M_data(), __s, __n);
          else if (__pos)
            _M_move(_M_data(), __s, __n);
          _M_rep()->_M_set_length_and_sharable(__n);
          return *this;
        }
     }
{% endhighlight %}

比较人性化的是，std::string 会做 disjunct 判断。

{% highlight cpp %}
      // True if _Rep and source do not overlap.
      bool
      _M_disjunct(const _CharT* __s) const _GLIBCXX_NOEXCEPT
      {
        return (less<const _CharT*>()(__s, _M_data())
                || less<const _CharT*>()(_M_data() + this->size(), __s));
      }
{% endhighlight %}

如果当前 string overlap 或者被其他 string share 的话

{% highlight cpp %}
  template<typename _CharT, typename _Traits, typename _Alloc>
    basic_string<_CharT, _Traits, _Alloc>&
    basic_string<_CharT, _Traits, _Alloc>::
    _M_replace_safe(size_type __pos1, size_type __n1, const _CharT* __s,
                    size_type __n2)
    {
      _M_mutate(__pos1, __n1, __n2);
      if (__n2)
        _M_copy(_M_data() + __pos1, __s, __n2);
      return *this;
    }
{% endhighlight %}

\_M\_mutate 的作用是把 \_\_pos 开始到 \_\_len1 长度的这段变成 \_\_len2 长。（erase 都是在用 \_M\_mutate 做喔，这个抽象做的不错~）

{% highlight cpp %}
  template<typename _CharT, typename _Traits, typename _Alloc>
    void
    basic_string<_CharT, _Traits, _Alloc>::
    _M_mutate(size_type __pos, size_type __len1, size_type __len2)
    {
      const size_type __old_size = this->size();
      const size_type __new_size = __old_size + __len2 - __len1;
      const size_type __how_much = __old_size - __pos - __len1;
      if (__new_size > this->capacity() || _M_rep()->_M_is_shared())
        {
          // Must reallocate.
          const allocator_type __a = get_allocator();
          _Rep* __r = _Rep::_S_create(__new_size, this->capacity(), __a);
          if (__pos)
            _M_copy(__r->_M_refdata(), _M_data(), __pos);
          if (__how_much)
            _M_copy(__r->_M_refdata() + __pos + __len2,
                    _M_data() + __pos + __len1, __how_much);
          _M_rep()->_M_dispose(__a);
          _M_data(__r->_M_refdata());
        }
      else if (__how_much && __len1 != __len2)
        {
          // Work in-place.
          _M_move(_M_data() + __pos + __len2,
                  _M_data() + __pos + __len1, __how_much);
        }
      _M_rep()->_M_set_length_and_sharable(__new_size);
    }
{% endhighlight %}

如果原来的空间已经没法用的话，就重新分配做 copy，否则直接原地 move。
\_M\_copy 和 \_M\_move 的区别是什么呢？

{% highlight cpp %}
      static void
      _M_move(_CharT* __d, const _CharT* __s, size_type __n) _GLIBCXX_NOEXCEPT
      {
        if (__n == 1)
          traits_type::assign(*__d, *__s);
        else
          traits_type::move(__d, __s, __n);
      }
{% endhighlight %}

原来会调 traits 中的 move。我们暂且先不看 traits 的内容。

iterator 的 assign 会转给 replace。

{% highlight cpp %}
      template<class _InputIterator>
        basic_string&
        assign(_InputIterator __first, _InputIterator __last)
        { return this->replace(_M_ibegin(), _M_iend(), __first, __last); }
{% endhighlight %}

其实里面内容大多都重复了，基本上都是在借用 \_M\_mutate, \_M\_copy 这些东西做操作。就懒得一个一个继续看了。

在看的过程中，发现后面还有类似 \_S\_construct\_aux 这样的东西，但是并没有用到，联想到 vector 里面乱七八糟的代码。。。拿到这就是下 trunk no zuo no die？

有几个地方要提一下

{% highlight cpp %}
      iterator
      begin() // FIXME C++11: should be noexcept.
      {
        _M_leak();
        return iterator(_M_data());
      }

      const_iterator
      begin() const _GLIBCXX_NOEXCEPT
      { return const_iterator(_M_data()); }

      reference
      operator[](size_type __pos)
      {
        // Allow pos == size() both in C++98 mode, as v3 extension,
        // and in C++11 mode.
        _GLIBCXX_DEBUG_ASSERT(__pos <= size());
        // In pedantic mode be strict in C++98 mode.
        _GLIBCXX_DEBUG_PEDASSERT(__cplusplus >= 201103L || __pos < size());
        _M_leak();
        return _M_data()[__pos];
      }
{% endhighlight %}

注意到，在返回 reference 或者 nonconst iterator 的时候，会触发 \_M\_leak。

{% highlight cpp %}
      void
      _M_leak() // for use in begin() & non-const op[]
      {
        if (!_M_rep()->_M_is_leaked())
          _M_leak_hard();
      }
{% endhighlight %}

{% highlight cpp %}
  template<typename _CharT, typename _Traits, typename _Alloc>
    void
    basic_string<_CharT, _Traits, _Alloc>::
    _M_leak_hard()
    {
#if _GLIBCXX_FULLY_DYNAMIC_STRING == 0
      if (_M_rep() == &_S_empty_rep())
        return;
#endif
      if (_M_rep()->_M_is_shared())
        _M_mutate(0, 0, 0);
      _M_rep()->_M_set_leaked();
    }
{% endhighlight %}

调用了 \_M\_mutate，强制重新分配。也就是在 shared 的时候，返回 ref 和 nonconst iter 会触发 string copy。

后面还有各种 append, insert, erase, operator 等等，就略过了，看多了无聊= = 其实都差不多。

### 总结一下~
1. string 的代码比 vector 简洁的多，代码不是那么冗余，而且做了很多优化~ 比如 inputiterator 的 buffer，考虑 pagesize 和 malloc 的 header。
2. basic\_string 明明就可以当做 string 用啊？ 区别呢？ ternimal；string 只有一个 \_M\_dataplus 成员，指向一块 length, capacity, refcount, 和 length +1 的 内存区域，而 vector 则是 \_M\_start, \_M\_finish, \_M\_end\_of\_storage。其实差别并不大，string 的内存做的更风骚而已，而且多了引用计数的操作。不过 string 没有做 uninitialize_copy 这种优化。
