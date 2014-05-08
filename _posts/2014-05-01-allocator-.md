---
layout: post
title: "allocator 篇"
description: ""
category: C++
tags: [C++, STL, code reading]
---
{% include JB/setup %}
allocator，一般情况下我们都不会见到或用到。不过大概也清楚，container 们基本都有一个模板参数，比如说 vector 的。

{% highlight cpp %}
template<
    class T,
    class Allocator = std::allocator<T>
> class vector;
{% endhighlight %}

第二个模板参数就是 allocator, 默认是 std::allocator。allocator 是用来分配内存的，也就是在你觉得默认的分配内存方式效率等方面存在问题的时候，你可以自己 customize 一个更好的 allocator。

关于 allocator 更多内的介绍可以 <a href="http://en.wikipedia.org/wiki/Allocator_(C++)">wiki</a> 。

<!--more-->

allocator 也有很蛋疼的地方。allocator 作为模板参数，导致两个用不同 allocator 的 vector 不是一个类型，无法赋值（<del>类型不同怎么在一起</del>）。另外老标准是要求 allocator 是无状态的，这很难用。

C++11 之后，allocator 可以有状态，而所有操作需要通过 std::allocator\_traits. 来进行（真是蛋疼）。

而让人更疼的是，c++11 还引入了 [allocator\_arg] (http://www.open-std.org/JTC1/SC22/WG21/docs/papers/2008/n2554.pdf) 。原因呢，当初搞 std::tuple, std::function, std::pair 时候上面没加 allocator 的模板参数，于是现在想让他们在 allocator 里面分配怎么办？增加带 allocator\_arg  参数构造函数，这个构造函数有 Alloc 模板参数，提供 allocator。（蛋疼。不过目前  allocator\_arg 还没有被引入 std::pair ）

std::scoped\_allocator\_adaptor。这货暂时不想吊他。

附上一些 allocator 的参考资料 
* [n1850](http://www.open-std.org/jtc1/sc22/wg21/docs/papers/2005/n1850.pdf)
* [improving perfomance with custom pool allocator](http://www.drdobbs.com/cpp/improving-performance-with-custom-pool-a/184406243?pgno=1)
* [what are allocators good for?](http://www.drdobbs.com/the-standard-librarian-what-are-allocato/184403759)

暂时不想深究 allocator，只是想解决一下之前 shared\_ptr 里面 inplace 分配的问题。所以不做过多的分析，只搞明白 allocator 和 trait 是怎么用的好了。

来到 include/bits/allocator.h

总是说标准库里面会做一些蛋疼的事情，比如说 allocator 也有对 void 的特化。
{% highlight cpp %}
  template<>
    class allocator<void>
{% endhighlight %}

{% highlight cpp %}
  template<typename _Tp>
    class allocator: public __allocator_base<_Tp>
    {
   public:
      typedef size_t size_type;
      typedef ptrdiff_t difference_type;
      typedef _Tp* pointer;
      typedef const _Tp* const_pointer;
      typedef _Tp& reference;
      typedef const _Tp& const_reference;
      typedef _Tp value_type;
      template<typename _Tp1>
        struct rebind
        { typedef allocator<_Tp1> other; };
#if __cplusplus >= 201103L
      // _GLIBCXX_RESOLVE_LIB_DEFECTS
      // 2103. std::allocator propagate_on_container_move_assignment
      typedef true_type propagate_on_container_move_assignment;
#endif
      allocator() throw() { }
      allocator(const allocator& __a) throw()
      : __allocator_base<_Tp>(__a) { }
      template<typename _Tp1>
        allocator(const allocator<_Tp1>&) throw() { }
      ~allocator() throw() { }
      // Inherit everything else.
    };
{% endhighlight %}

恩，又是一层包装，暂时找不到封装的理由。

{% highlight cpp %}
  template<typename _T1, typename _T2>
    inline bool
    operator==(const allocator<_T1>&, const allocator<_T2>&)
    _GLIBCXX_USE_NOEXCEPT
    { return true; }
  template<typename _Tp>
    inline bool
    operator==(const allocator<_Tp>&, const allocator<_Tp>&)
    _GLIBCXX_USE_NOEXCEPT
    { return true; }
  template<typename _T1, typename _T2>
    inline bool
    operator!=(const allocator<_T1>&, const allocator<_T2>&)
    _GLIBCXX_USE_NOEXCEPT
    { return false; }
  template<typename _Tp>
    inline bool
    operator!=(const allocator<_Tp>&, const allocator<_Tp>&)
    _GLIBCXX_USE_NOEXCEPT
    { return false; }
{% endhighlight %}

为了简化 allocator 和提升效率，比较 operator 是这样做的。

注意到
{% highlight cpp %}
#if _GLIBCXX_EXTERN_TEMPLATE
  extern template class allocator<char>;
  extern template class allocator<wchar_t>;
#endif
{% endhighlight %}

而在 src/c++98/allocator-inst.cc 中进行显示实例化
{% highlight cpp %}
namespace std _GLIBCXX_VISIBILITY(default)
{
_GLIBCXX_BEGIN_NAMESPACE_VERSION
  template class allocator<char>;
  template class allocator<wchar_t>;
_GLIBCXX_END_NAMESPACE_VERSION
} // namespace
{% endhighlight %}

这是为 std::string 做的。这样显式实例化可以让你使用 std::string 时候，不用再生成 allocator 模板的代码，而直接链接到 lib 里面的代码。

外面还有点代码无关紧要，先进 \_\_allocator\_base 里面来看。
\_\_allocator\_base 应该在 #include &lt;bits/c++allocator.h&gt; 里面，然而目前并没有这个文件。。。makefile 搞得鬼

Makefile.am
{% highlight makefile %}
 $(LN_S) ${glibcxx_srcdir}/$(ALLOCATOR_H) c++allocator.h || true ;\
{% endhighlight %}

configure
{% highlight makefile %}
  # Set configure bits for specified locale package
  case ${enable_libstdcxx_allocator_flag} in
    bitmap)
      ALLOCATOR_H=config/allocator/bitmap_allocator_base.h
      ALLOCATOR_NAME=__gnu_cxx::bitmap_allocator
      ;;
    malloc)
      ALLOCATOR_H=config/allocator/malloc_allocator_base.h
      ALLOCATOR_NAME=__gnu_cxx::malloc_allocator
      ;;
    mt)
      ALLOCATOR_H=config/allocator/mt_allocator_base.h
      ALLOCATOR_NAME=__gnu_cxx::__mt_alloc
      ;;
    new)
      ALLOCATOR_H=config/allocator/new_allocator_base.h
      ALLOCATOR_NAME=__gnu_cxx::new_allocator
      ;;
    pool)
      ALLOCATOR_H=config/allocator/pool_allocator_base.h
      ALLOCATOR_NAME=__gnu_cxx::__pool_alloc
      ;;
  esac
{% endhighlight %}

看来是对 new, pool, mt, bitmap 这几种做了封装。我想我们的 default 应该是 new allocator 吧~

{% highlight makefile %}
  if test $enable_libstdcxx_allocator_flag = auto; then
    case ${target_os} in
      linux* | gnu* | kfreebsd*-gnu | knetbsd*-gnu)
        enable_libstdcxx_allocator_flag=new
        ;;
      *)
        enable_libstdcxx_allocator_flag=new
        ;;
    esac
  fi
{% endhighlight %}

有空可以研究一下 bitmap 和 pool，mt 这几个 allocator 是干嘛的。先看 new 的吧。

{% highlight cpp %}
  template<typename _Tp>
    using __allocator_base = __gnu_cxx::new_allocator<_Tp>;
{% endhighlight %}

来到 ext/new\_allocator.h，废话不看，直接往下拉

{% highlight cpp %}
      pointer
      address(reference __x) const _GLIBCXX_NOEXCEPT
      { return std::__addressof(__x); }
      const_pointer
      address(const_reference __x) const _GLIBCXX_NOEXCEPT
      { return std::__addressof(__x); }
      // NB: __n is permitted to be 0. The C++ standard says nothing
      // about what the return value is when __n == 0.
      pointer
      allocate(size_type __n, const void* = 0)
      {
        if (__n > this->max_size())
          std::__throw_bad_alloc();
        return static_cast<_Tp*>(::operator new(__n * sizeof(_Tp)));
      }
      // __p is not permitted to be a null pointer.
      void
      deallocate(pointer __p, size_type)
      { ::operator delete(__p); }
      size_type
      max_size() const _GLIBCXX_USE_NOEXCEPT
      { return size_t(-1) / sizeof(_Tp); }
#if __cplusplus >= 201103L
      template<typename _Up, typename... _Args>
        void
        construct(_Up* __p, _Args&&... __args)
        { ::new((void *)__p) _Up(std::forward<_Args>(__args)...); }
      template<typename _Up>
        void
        destroy(_Up* __p) { __p->~_Up(); }
#else
{% endhighlight %}

allocator 的内容已经尽收眼底。address 是拿地址，allocate 是分配 n 个对象的内存，deallocate 释放内存。
construct 则是 placement new 掉构造，destroy 则是调析构。

allocate 大概的功能已经清楚了，我们来看 allocator\_trait。

include/bits/allocate\_trait
其实也没什么内容，就是一层代理
{% highlight cpp %}
      static pointer
      allocate(_Alloc& __a, size_type __n)
      { return __a.allocate(__n); }

      static pointer
      allocate(_Alloc& __a, size_type __n, const_void_pointer __hint)
      { return _S_allocate(__a, __n, __hint); }

      static void deallocate(_Alloc& __a, pointer __p, size_type __n)
      { __a.deallocate(__p, __n); }

      template<typename _Tp, typename... _Args>
        static auto construct(_Alloc& __a, _Tp* __p, _Args&&... __args)
        -> decltype(_S_construct(__a, __p, std::forward<_Args>(__args)...))
        { _S_construct(__a, __p, std::forward<_Args>(__args)...); }

      template <class _Tp>
        static void destroy(_Alloc& __a, _Tp* __p)
        { _S_destroy(__a, __p); }
{% endhighlight %}

\_S\_allocate 可以带 hint，当然这不是我们现在关心的重点。 看下 \_S\_construct

{% highlight cpp %}
      template<typename _Tp, typename... _Args>
        static _Require<__has_construct<_Tp, _Args...>>
        _S_construct(_Alloc& __a, _Tp* __p, _Args&&... __args)
        { __a.construct(__p, std::forward<_Args>(__args)...); }
      template<typename _Tp, typename... _Args>
        static
        _Require<__and_<__not_<__has_construct<_Tp, _Args...>>,
                               is_constructible<_Tp, _Args...>>>
        _S_construct(_Alloc&, _Tp* __p, _Args&&... __args)
        { ::new((void*)__p) _Tp(std::forward<_Args>(__args)...); }
{% endhighlight %}

原来是重载。不过 \_\_has\_construct 和 is\_constructible 有什么区别呢？

{% highlight cpp %}
      template<typename _Tp, typename... _Args>
        struct __construct_helper
        {
          template<typename _Alloc2,
            typename = decltype(std::declval<_Alloc2*>()->construct(
                  std::declval<_Tp*>(), std::declval<_Args>()...))>
            static true_type __test(int);
          template<typename>
            static false_type __test(...);
          using type = decltype(__test<_Alloc>(0));
        };
      template<typename _Tp, typename... _Args>
        using __has_construct
          = typename __construct_helper<_Tp, _Args...>::type;
{% endhighlight %}

原来 \_\_has\_construct 是判断 allocator 上是否能 construct 这个东东。不过按理说 allocator 的 construct 也是掉 placement new，两者会有不同么？

好吧，关于这点要回到 allocator\_trait 的意义。The allocator\_traits class template provides the standardized way to access various properties of allocators。

于是当 Alloc 不存在 construct 函数的时候。。。allocate\_trait 就主动帮忙。destroy 也是同理。

还有一个东西，rebind，昨天就卡在这里。

{% highlight cpp %}
      template<typename _Tp>
        using rebind_alloc = typename __alloctr_rebind<_Alloc, _Tp>::__type;
      template<typename _Tp>
        using rebind_traits = allocator_traits<rebind_alloc<_Tp>>;
{% endhighlight %}

来看 \_\_alloctr\_rebind
{% highlight cpp %}
  template<typename _Alloc, typename _Tp,
           bool = __alloctr_rebind_helper<_Alloc, _Tp>::__type::value>
    struct __alloctr_rebind;
  template<typename _Alloc, typename _Tp>
    struct __alloctr_rebind<_Alloc, _Tp, true>
    {
      typedef typename _Alloc::template rebind<_Tp>::other __type;
    };
  template<template<typename, typename...> class _Alloc, typename _Tp,
           typename _Up, typename... _Args>
    struct __alloctr_rebind<_Alloc<_Up, _Args...>, _Tp, false>
    {
      typedef _Alloc<_Tp, _Args...> __type;
    };
{% endhighlight %}

看一下  \_\_alloctr\_rebind\_helper&lt;\_Alloc, \_Tp&gt;::\_\_type::value 什么时候是 true 什么时候是 false

{% highlight cpp %}
  template<typename _Alloc, typename _Tp>
    class __alloctr_rebind_helper
    {
      template<typename _Alloc2, typename _Tp2>
        static constexpr true_type
        _S_chk(typename _Alloc2::template rebind<_Tp2>::other*);
      template<typename, typename>
        static constexpr false_type
        _S_chk(...);
    public:
      using __type = decltype(_S_chk<_Alloc, _Tp>(nullptr));
    };
{% endhighlight %}

也就是看 \_Alloc2::template rebind&lt;\_Tp2&gt;::other* 是否存在。 之前没有注意看 allocator 里面的 rebind 成员，回头喵一眼。

{% highlight cpp %}
      template<typename _Tp1>
        struct rebind
        { typedef new_allocator<_Tp1> other; };
{% endhighlight %}

好吧，也就是 rebind 了另一个类型的 allocator。反正 new allocator 没状态，随便给你无所谓。

等下， \_Alloc2::template 这种东西第一次见到，为什么要这么写？（我很土的）这是因为 \_Alloc2 现在还是模板类型嘛，还木有 \_Tp，而 rebind 并不需要类模板参数 \_Tp，给一个 \_Tp1 就够了。

\_\_alloctr\_rebind\_helper 在判断 allocator 里面是否有 rebind 支持。如果有 rebind 的话，后面的 \_\_alloctr\_rebind 就会把这个 rebind 提供出去；如果没有呢（false），则会自己定义一个 typedef \_Alloc&lt;\_Tp, \_Args...&gt; \_\_type; ，将 \_Args... bind 到 allocator 上，allocator&lt;\_Tp&gt; 变成了 Allocator&lt;\_Tp, \_Args ...&gt;。

于是跳到最前面， rebind\_alloc 就是 rebind 之后的 allocator 类型啦，rebind\_traits 则是这个 allocator 上加 trait 之后的结果。

那么，现在是时候接过昨天的烂尾工程了

还是 \_\_shared\_count 的构造函数。
{% highlight cpp %}
      template<typename _Tp, typename _Alloc, typename... _Args>
        __shared_count(_Sp_make_shared_tag, _Tp*, const _Alloc& __a,
                       _Args&&... __args)
        : _M_pi(0)
        {
          typedef _Sp_counted_ptr_inplace<_Tp, _Alloc, _Lp> _Sp_cp_type;
          typedef typename allocator_traits<_Alloc>::template
            rebind_traits<_Sp_cp_type> _Alloc_traits;
          typename _Alloc_traits::allocator_type __a2(__a);
          _Sp_cp_type* __mem = _Alloc_traits::allocate(__a2, 1);
          __try
            {
              _Alloc_traits::construct(__a2, __mem, std::move(__a),
                    std::forward<_Args>(__args)...);
              _M_pi = __mem;
            }
          __catch(...)
            {
              _Alloc_traits::deallocate(__a2, __mem, 1);
              __throw_exception_again;
            }
        }
{% endhighlight %}

首先定义了 \_Sp\_cp\_type 就是我们 counter 的 type，然后 rebind\_traits 将原来 \_Alloc&lt;\_Tp&gt; rebind 到了 \_Sp\_cp\_type 变成了 \_Alloc&lt;\_Sp\_cp\_type&gt;，然后用原来的 \_Alloc \_\_a 构造一个新的 \_Alloc&lt;\_Sp\_cp\_type&gt; \_\_a2，接下来就是 construct。发现 construct 会接受 \_Alloc&lt;\_Tp&gt;。

{% highlight cpp %}
      template<typename... _Args>
        _Sp_counted_ptr_inplace(_Alloc __a, _Args&&... __args)
        : _M_impl(__a)
        {
          // _GLIBCXX_RESOLVE_LIB_DEFECTS
          // 2070. allocate_shared should use allocator_traits<A>::construct
          allocator_traits<_Alloc>::construct(__a, _M_ptr(),
              std::forward<_Args>(__args)...); // might throw
        }
{% endhighlight %}

再看 Impl
{% highlight cpp %}
      class _Impl : _Sp_ebo_helper<0, _Alloc>
      {
        typedef _Sp_ebo_helper<0, _Alloc> _A_base;
      public:
        explicit _Impl(_Alloc __a) noexcept : _A_base(__a) { }
        _Alloc& _M_alloc() noexcept { return _A_base::_S_get(*this); }
        __gnu_cxx::__aligned_buffer<_Tp> _M_storage;
      }; 
{% endhighlight %}
注

\_Sp\_ebo\_helper 是做 empty base optimization 的，\_M\_storage 就是 \_Tp 真正存在的地方。 注意到这里还用到 \_\_aligned\_buffer，rebind 之后 counter 部分应该是在 \_Tp 的后面，用对齐 buffer 是为了对齐 counter 部分。

相应 \_M\_destroy 和 \_M\_dispose 里面也就是各种的 deallocate 和  destroy 了。

allocate 分配的是连续的内存，只有在 \_M\_destroy 的时候才会最后释放。所以说，inplace 也有一个坏处，就是只要存在 weak\_ptr 时，就算 shared\_ptr 都挂掉，对象已经失效，但内存还在占用着。

好了，昨天的烂尾补上了~~

### 总结一下
1. lib 的设计真是一件非常蛋碎的事情，稍有不慎就各种败笔（allocator可算一例?）
2. allocator 的初衷是好的，不过日常生活中一般用不到啦~ 然后之前实习的时候有用 mem\_pool，也没借助 allocator 而是直接在 mem\_pool 上 new 什么的。还是看怎么方便怎么来
3. ebo 可谓在 stl 里被用烂了
4. 找时间可以分析一下几种 allocator，mt（多线程）的 mem\_pool 应该比较好玩。不过现在大家都用 tcmalloc 这种东西了。。。。。