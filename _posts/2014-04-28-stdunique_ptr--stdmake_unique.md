---
layout: post
title: "std::unique_ptr &amp; std::make_unique"
description: ""
category: C++
tags: [C++, STL, code reading]
---
{% include JB/setup %}

今天继续来一弹，这次是比较简单的 [unqiue\_ptr](http://en.cppreference.com/w/cpp/memory/unique\_ptr)。
用来持有 ownership 的指针。unique 顾名思义，不可以像 shared 随便来拿。

c++11 的 rvalue ref 和 move 无疑是让 unique\_ptr 方便了许多，当然没有他们的时候，
unqiue\_ptr [也是可以被模拟出来的](http://home.roadrunner.com/~hinnant/unique\_ptr03.html)

不过先不管这些，直接来看新标准新代码。还是 libstdc++v3。为了简单起见，这里只说最简单的 unique\_ptr，不看 数组版的 unique\_ptr。

<!--more-->
include/bits/unique\_ptr.h line 128
{% highlight cpp %}
  /// 20.7.1.2 unique_ptr for single objects.
  template <typename _Tp, typename _Dp = default_delete<_Tp> >
    class unique_ptr
{% endhighlight %}

unqiue\_ptr 接受两个模板参数，一个就是 ptr 所指类型，另一个是 deleter，也就是 release 要在 ptr 上调用的类似析构一样的函数。

索性先看一下 default\_delete 是怎样的？其实随便 yy 也想的到，这应该就是 delete 包装了一下。

{% highlight cpp %}
  /// Primary template of default_delete, used by unique_ptr
  template<typename _Tp>
    struct default_delete
    {
      /// Default constructor
      constexpr default_delete() noexcept = default;
      /** @brief Converting constructor.
       *
       * Allows conversion from a deleter for arrays of another type, @p _Up,
       * only if @p _Up* is convertible to @p _Tp*.
       */
      template<typename _Up, typename = typename
               enable_if<is_convertible<_Up*, _Tp*>::value>::type>
        default_delete(const default_delete<_Up>&) noexcept { }
      /// Calls @c delete @p __ptr
      void
      operator()(_Tp* __ptr) const
      {
        static_assert(!is_void<_Tp>::value,
                      "can't delete pointer to incomplete type");
        static_assert(sizeof(_Tp)>0,
                      "can't delete pointer to incomplete type");
        delete __ptr;
      }
    };

{% endhighlight %}

似乎有奇奇怪怪的东西混了进来。抛开 private 中的 trait 先不看，先来下面的构造函数。

constexpr 的 default 构造函数，关于 constexpr http://en.cppreference.com/w/cpp/language/constexpr。
constexpr，noexcept 这些都是为了尽量给编译器更多的优化空间。

下面的构造函数

{% highlight cpp %}
enable_if<is_convertible<_Up*, _Tp*>::value>::type
{% endhighlight %}

类似的方法之前有见过。也就是在 \_Up 可以被转换成 \_Tp 的时候，提供这个从 \_Up deleter 到 \_Tp deleter 的构造。
可以从 default\_delete&lt;Derived&gt; 构造 default\_delete&lt;Base&gt;

下面的 operator 就是干活的啦。里面就是 delete。当然还有 static\_assert 来做检查类型的完整性。

default\_delete 和 unique\_ptr 一样，下面有一个数组版的，略过。我们接着来看 unique\_ptr。

{% highlight cpp %}
  /// 20.7.1.2 unique_ptr for single objects.
  template <typename _Tp, typename _Dp = default_delete<_Tp> >
    class unique_ptr
    {
      // use SFINAE to determine whether _Del::pointer exists
      class _Pointer
      {
        template<typename _Up>
          static typename _Up::pointer __test(typename _Up::pointer*);
        template<typename _Up>
          static _Tp* __test(...);
        typedef typename remove_reference<_Dp>::type _Del;
      public:
        typedef decltype(__test<_Del>(0)) type;
      };
      typedef std::tuple<typename _Pointer::type, _Dp> __tuple_type;
      __tuple_type _M_t;
{% endhighlight %}

可能看到这里有点困惑， 为什么要 deleter::type::pointer？ 这就要看  unqiue\_ptr 的说明了

> pointer std::remove\_reference&lt;Deleter&gt;::type::pointer if that type exists, otherwise T\*

也就是说，unqiue\_ptr 里面实际 hold 的 pointer 是首先选择 deleter::type::pointer ，如果不存在则用 T\*。
这里再次用 SFINAE 来决定 deleter::type::pointer 是否存在。

注意看 \_Pointer::type。

{% highlight cpp %}
typedef decltype(__test<_Del>(0)) type;
{% endhighlight %}

再看 \_\_test 函数的重载，就一目了然了。巧妙的利用了重载函数的返回值来确定 pointer 类型。

继续看下面 unqiue\_ptr 的成员。

{% highlight cpp %}
      typedef std::tuple<typename _Pointer::type, _Dp> __tuple_type;
      __tuple_type _M_t;
{% endhighlight %}

原来 unqiue\_ptr 里面把实际的指针和deleter结构封成了一个 tuple，作为成员。这也是 unqiue\_ptr 唯一的成员。
咦，为什么要这样做呢？直接做成两个成员不是也可以。继续往下，看看能不能找到答案。

{% highlight cpp %}
    public:
      typedef typename _Pointer::type pointer;
      typedef _Tp element_type;
      typedef _Dp deleter_type;
      // Constructors.
      constexpr unique_ptr() noexcept
      : _M_t()
      { static_assert(!is_pointer<deleter_type>::value,
                     "constructed with null function pointer deleter"); }
      explicit
      unique_ptr(pointer __p) noexcept
      : _M_t(__p, deleter_type())
      { static_assert(!is_pointer<deleter_type>::value,
                     "constructed with null function pointer deleter"); }

      unique_ptr(pointer __p,
          typename conditional<is_reference<deleter_type>::value,
            deleter_type, const deleter_type&>::type __d) noexcept
      : _M_t(__p, __d) { }

      unique_ptr(pointer __p,
          typename remove_reference<deleter_type>::type&& __d) noexcept
      : _M_t(std::move(__p), std::move(__d))
      { static_assert(!std::is_reference<deleter_type>::value,
                      "rvalue deleter bound to reference"); }

{% endhighlight %}

都是很正常的构造，static\_assert 对模板 deleter 做了防范。如果 deleter 就是一个函数指针的话，不可以做这种默认构造（deleter 都是 null 你想死？）。
后面的 static reference 是在防范在 deleter\_type 是一个 reference 的时候拿到了 rvalue，引用临时量就挂了~~

{% highlight cpp %}
void dl(int *a) {
    delete a;
}
unique_ptr<int, void(*)(int*)> a(new int(1));   // No
unique_ptr<int, void(*)(int*)> a(new int(1), &dl);   // Yes
{% endhighlight %}

接下来还有 nullptr\_t。 nullptr\_t 是 nullptr 的 type，stl 的指针类似物构造都对 nullptr\_t 做了处理，算是一个小优化。c++11 首选 nullptr 喔。
{% highlight cpp %}
      /// Creates a unique_ptr that owns nothing.
      constexpr unique_ptr(nullptr_t) noexcept : unique_ptr() { }
{% endhighlight %}

还有 move ctor
{% highlight cpp %}
      /// Move constructor.
      unique_ptr(unique_ptr&& __u) noexcept
      : _M_t(__u.release(), std::forward<deleter_type>(__u.get_deleter())) { }
{% endhighlight %}

也就是 a(unqiue\_ptr&lt;Type&gt;(....)) 的时候，会把 b 的 pointer  release 下来拿在自己手里，还会拿到对方的 deleter。
既然看到了 release，直接跳到后面看一眼 release。

{% highlight cpp %}
      pointer
      release() noexcept
      {
        pointer __p = get();
        std::get<0>(_M_t) = pointer();
        return __p;
      }
{% endhighlight %}

顺便看下 get
{% highlight cpp %}
      pointer
      get() const noexcept
      { return std::get<0>(_M_t); }
{% endhighlight %}
并没有什么特别的。

回到刚才的点，接着看构造。

{% highlight cpp %}
      template<typename _Up, typename _Ep, typename = _Require<
               is_convertible<typename unique_ptr<_Up, _Ep>::pointer, pointer>,
               __not_<is_array<_Up>>,
               typename conditional<is_reference<_Dp>::value,
                                    is_same<_Ep, _Dp>,
                                    is_convertible<_Ep, _Dp>>::type>>
        unique_ptr(unique_ptr<_Up, _Ep>&& __u) noexcept
        : _M_t(__u.release(), std::forward<_Ep>(__u.get_deleter()))
        { }
{% endhighlight %}
这里还是用模板 trait，为了处理 unqiue\_ptr&lt;Base&gt;(new Derived) 这种情况。

下面是 dtor
{% highlight cpp %}
      /// Destructor, invokes the deleter if the stored pointer is not null.
      ~unique_ptr() noexcept
      {
        auto& __ptr = std::get<0>(_M_t);
        if (__ptr != nullptr)
          get_deleter()(__ptr);
        __ptr = pointer();
      }
{% endhighlight %}
先拿到指针后，调用 deleter 进行析构，然后把指针清 0.

后面则是 operator=(&&) ，处理 a = std::move(b)。
{% highlight cpp %}
      unique_ptr&
      operator=(unique_ptr&& __u) noexcept
      {
        reset(__u.release());
        get_deleter() = std::forward<deleter_type>(__u.get_deleter());
        return *this;
      }
{% endhighlight %}

其中的 reset 是先做 swap，再把原来的 pointer 上掉 deleter。
{% highlight cpp %}
      void
      reset(pointer __p = pointer()) noexcept
      {
        using std::swap;
        swap(std::get<0>(_M_t), __p);
        if (__p != pointer())
          get_deleter()(__p);
      }
{% endhighlight %}

后面还有 Derived class， nullptr 情况的 operator=(&&)，就不一一说明了，跟之前都相似。

还有平淡无奇的 operator* 和 operator-&gt;
{% highlight cpp %}
      /// Dereference the stored pointer.
      typename add_lvalue_reference<element_type>::type
      operator*() const
      {
        _GLIBCXX_DEBUG_ASSERT(get() != pointer());
        return *get();
      }
      /// Return the stored pointer.
      pointer
      operator->() const noexcept
      {
        _GLIBCXX_DEBUG_ASSERT(get() != pointer());
        return get();
      }
{% endhighlight %}

不过话说回来，unique\_ptr 的操作符重载和各种构造函数真是够全的，数组版的 unique\_ptr 的还有 operator\[\]。
可以拿来当模板学习。

注意到  typename add\_lvalue\_reference&lt;element\_type&gt;::type，其实这里直接上 element\_type& 也可以的。

后面还有 operator bool，让你尽情的 if。
{% highlight cpp %}
      /// Return @c true if the stored pointer is not null.
      explicit operator bool() const noexcept
      { return get() == pointer() ? false : true; }
{% endhighlight %}
 ，
最后收尾的是 swap，还有把拷贝构造和 operator= 干掉了。

{% highlight cpp %}
      /// Exchange the pointer and deleter with another object.
      void
      swap(unique_ptr& __u) noexcept
      {
        using std::swap;
        swap(_M_t, __u._M_t);
      }
      // Disable copy from lvalue.
      unique_ptr(const unique_ptr&) = delete;
      unique_ptr& operator=(const unique_ptr&) = delete;
{% endhighlight %}

当然后面还有各种 operator== 等等。
一路看下来，普普通通，比较核心的部分就是 && 和 move 这些东西。
对了之前还有一个问题没解决，就是为什么用 tuple 封装一下。感觉就做成成员完全没问题啊。。

我们换个方向，看看其他 std 也是这么实现的么？看看 clang 的 libcxx。

include/memory
line 2456
{% highlight cpp %}
template <class _Tp, class _Dp = default_delete<_Tp> >
class _LIBCPP_TYPE_VIS_ONLY unique_ptr
{
public:
    typedef _Tp element_type;
    typedef _Dp deleter_type;
    typedef typename __pointer_type<_Tp, deleter_type>::type pointer;
private:
    __compressed_pair<pointer, deleter_type> __ptr_;
{% endhighlight %}

libcxx 的实现没用 tuple，而是用了 \_\_compress\_pair，我们追上去看看。可能熟悉 boost 的人看到这里已经知道他在干嘛了，= = 但是我还不知道啊。。。。

line 2300
{% highlight cpp %}
template <class _T1, class _T2>
class __compressed_pair
    : private __libcpp_compressed_pair_imp<_T1, _T2>
{% endhighlight %}

原来是在外面包了一层。跟上去，发现问题有一些复杂
{% highlight cpp %}
template <class _T1, class _T2, unsigned = __libcpp_compressed_pair_switch<_T1, _T2>::value>
class __libcpp_compressed_pair_imp;

template <class _T1, class _T2>
class __libcpp_compressed_pair_imp<_T1, _T2, 0>

template <class _T1, class _T2>
class __libcpp_compressed_pair_imp<_T1, _T2, 1>
    : private _T1

template <class _T1, class _T2>
class __libcpp_compressed_pair_imp<_T1, _T2, 2>
    : private _T2

template <class _T1, class _T2>
class __libcpp_compressed_pair_imp<_T1, _T2, 3>
    : private _T1 , private _T2
{% endhighlight %}
竟然用了 private 继承，这又是为什么呢？为何不直接将 T1, T2 做成成员？
看一下 \_\_libcpp\_compressed\_pair\_switch。通过这个 trait，在编译期的时候会根据 T1, T2 的类型选择对应的 pair\_impl。

line 1905
{% highlight cpp %}
template <class _T1, class _T2, bool = is_same<typename remove_cv<_T1>::type,
                                                     typename remove_cv<_T2>::type>::value,
                                bool = is_empty<_T1>::value
#if __has_feature(is_final)
                                       && !__is_final(_T1)
#endif
                                ,
                                bool = is_empty<_T2>::value
#if __has_feature(is_final)
                                       && !__is_final(_T2)
#endif
         >
struct __libcpp_compressed_pair_switch;
{% endhighlight %}

真是变态啊，继续看下面。

{% highlight cpp %}
template <class _T1, class _T2, bool IsSame>
struct __libcpp_compressed_pair_switch<_T1, _T2, IsSame, false, false> {enum {value = 0};};
template <class _T1, class _T2, bool IsSame>
struct __libcpp_compressed_pair_switch<_T1, _T2, IsSame, true, false> {enum {value = 1};};
template <class _T1, class _T2, bool IsSame>
struct __libcpp_compressed_pair_switch<_T1, _T2, IsSame, false, true> {enum {value = 2};};
template <class _T1, class _T2>
struct __libcpp_compressed_pair_switch<_T1, _T2, false, true, true> {enum {value = 3};};
template <class _T1, class _T2>
struct __libcpp_compressed_pair_switch<_T1, _T2, true, true, true> {enum {value = 1};};
template <class _T1, class _T2, unsigned = __libcpp_compressed_pair_switch<_T1, _T2>::value>
class __libcpp_compressed_pair_imp;
{% endhighlight %}

事情到这里就清晰了。在 T1 和 T2 都是 is\_empty（http://en.cppreference.com/w/cpp/types/is\_empty） 且 不 is\_final（是否可继承） 时候就会选择进行 private 继承的实现，而如果其中一方不是的话，则会根据另一方的情况，尽量选择 private 继承的实现。

C++ 竟然都要有 final 了，http://en.cppreference.com/w/cpp/language/final。 再联想一下 override 的出现，这是逐渐向 C# 接轨的节奏么？

看到这里，事情似乎变得更复杂了，这个 compress pair 总是想尽量 private inherit T1 和 T2。私有继承有什么作用呢？为什么这个叫做 compressed\_pair？

empty base optimization http://en.cppreference.com/w/cpp/language/ebo。 这就是问题的答案。C++ 中， sizeof(anytype) &gt; 0，就算一个空的 struct 也会 sizeof(emptyStruct) == 1。而 deleter 经常是一个带 operator() 没有成员的 struct，而作为成员的话，总会多出来这个 1 的大小，但是如果是 private 继承，编译器会把 empty base class 这个空间优化掉~~~ 这就是用 compressed\_pair 的目的。

注意到
\[quote\]
Empty base optimization is prohibited if one of the empty base classes is also the type of the first non-static data member, or the base of the type of the first non-static data member since the two base subobjects have the same type, and therefore are required to have different addresses within the object representation of the most derived type.
\[/quote\]

所以类型相同的时候，会只对其中一个 做 private 继承。

到这里，明白了 compress\_pair 的作用以及为什么 libcxx 里面会用 compressed\_pair 对 pointer 和 deleter 进行包装。回过头，libstdc++ 用 tuple 是何解呢？不妨看一下 tuple 是怎么实现的。

include/tr1/tuple
{% highlight cpp %}
  template<int _Idx, typename... _Elements>
    struct _Tuple_impl;
  /**
   * Zero-element tuple implementation. This is the basis case for the
   * inheritance recursion.
   */
  template<int _Idx>
    struct _Tuple_impl<_Idx> { };
  /**
   * Recursive tuple implementation. Here we store the @c Head element
   * and derive from a @c Tuple_impl containing the remaining elements
   * (which contains the @c Tail).
   */
  template<int _Idx, typename _Head, typename... _Tail>
    struct _Tuple_impl<_Idx, _Head, _Tail...>
    : public _Tuple_impl<_Idx + 1, _Tail...>
{% endhighlight %}

其意不言自明。

then, make\_unique
make\_unique 也有单机版和数组版两种。

{% highlight cpp %}
    auto unique_var = make_unique<int>(3);
    auto unique_array = make_unique<int[]>(3);
{% endhighlight %}

分别是一个 3，和一个长度为 3 的动态数组。
然而 make\_unique 是不允许构造定长数组的（不能匹配到 int\[N\] 上）

{% highlight cpp %}
auto err = make_unique<int[3]>(); // error!
{% endhighlight %}

实现分为两部分
首先是 \_MakeUniq 结构
{% highlight cpp %}
#if __cplusplus > 201103L
  template<typename _Tp>
    struct _MakeUniq
    { typedef unique_ptr<_Tp> __single_object; };
  template<typename _Tp>
    struct _MakeUniq<_Tp[]>
    { typedef unique_ptr<_Tp[]> __array; };
  template<typename _Tp, size_t _Bound>
    struct _MakeUniq<_Tp[_Bound]>
    { struct __invalid_type { }; };
  /// std::make_unique for single objects
{% endhighlight %}

然后是 make\_unique 函数，几个重载。
{% highlight cpp %}
  template<typename _Tp, typename... _Args>
    inline typename _MakeUniq<_Tp>::__single_object
    make_unique(_Args&&... __args)
    { return unique_ptr<_Tp>(new _Tp(std::forward<_Args>(__args)...)); }
  /// std::make_unique for arrays of unknown bound
  template<typename _Tp>
    inline typename _MakeUniq<_Tp>::__array
    make_unique(size_t __num)
    { return unique_ptr<_Tp>(new typename remove_extent<_Tp>::type[__num]()); }
  /// Disable std::make_unique for arrays of known bound
  template<typename _Tp, typename... _Args>
    inline typename _MakeUniq<_Tp>::__invalid_type
    make_unique(_Args&&...) = delete;
#endif
{% endhighlight %}

\_MakeUnqi&lt;\_Tp&gt; 是被拿来做返回类型匹配的 helper。匹配优先级如下：
1. 在 make\_unique&lt;T\[N\]&gt; 时， struct \_MakeUniq&lt;\_Tp\[\_Bound\]&gt; 匹配，得到 struct \_\_invalid\_type { }; ，而此时的函数 =delete，被干掉了。
2. 在 make\_unique&lt;T\[\]&gt; 时， struct \_MakeUniq&lt;\_Tp\[\]&gt; 匹配，得到 typedef unique\_ptr&lt;\_Tp\[\]&gt; \_\_array;
3. 在 make\_unique&lt;T&gt; 时，struct \_MakeUniq&lt;\_Tp&gt; 匹配，得到 typedef unique\_ptr&lt;\_Tp&gt; \_\_single\_object;

注意到这些模板函数签名在某些情况下可以相同的

{% highlight cpp %}
 auto unique_var = make_unique<size_t>();  // single vs. invalid
 auto unique_var = make_unique<size_t>(1); // array vs. single
{% endhighlight %}

单纯函数重载是搞不定这些的（参数表都相同怎么重载），而起到决议作用的恰恰上上面的 \_MakeUniq。\_MakeUniq 的模板重载决议发挥作用进行匹配。\[b\]这真是一件非常非常奇妙的事情，函数通过在返回类型上加 trait 进行重载。\[/b\]
\_\_invalid\_type， \_\_array，\_\_single\_object，他们指定了匹配的方向（T\[N\], T\[\], T）。

构造时候做的事情都很显而易见了。有一个小 trait， remove\_extent，功能是拿掉 T\[\] 中的 \[\] 得到 T。

### 总结一下~
1. 土人第一次学到 empty class optimization = =
2. trait 真的非常有意思。enable\_if, is\_base\_of, is\_convertible 等等。模板在编译器的多态非常强大，比如刚才编译器动态决定继承关系（或者说类型）。
3. 通过 unqiue\_ptr 复习各种操作符重载，move，swap ，构造等等的写法。
