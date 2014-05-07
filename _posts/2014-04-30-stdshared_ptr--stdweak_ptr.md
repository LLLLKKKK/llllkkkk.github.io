---
layout: post
title: "std::shared_ptr 与 std::weak_ptr"
description: ""
category: C++
tags: [C++, STL, code reading]
---
{% include JB/setup %}
《三体》想象力真的非常丰富啊~~ 打球归，感觉今天写不了太多了。。。。。

好我们继续。shared\_ptr 这么喜闻乐见我觉得就不用废话了，应该是最常用的零部件之一。
shared\_ptr 采用引用计数对 object 进行管理，引用计数的硬伤的无法解决循环引用的问题，比如说
A 包含指向 B 的指针，B 包含指向 A 的指针，无论怎样没法在 A B 都失效的时候释放他们两个。
所以有了 weak\_ptr ，也就是 A 包含 B 的 shared\_ptr， B 包含 A 的 weak\_ptr ，weak\_ptr 不会“增加引用计数”，不会形成循环应用，不过想使用 weak\_ptr 包含的东西时必须将其提升为 shared\_ptr。

[shared_ptr](http://en.cppreference.com/w/cpp/memory/shared_ptr)，[weak_ptr](http://en.cppreference.com/w/cpp/memory/weak_ptr)


libstdc++v3, include/bits/shared\_ptr.h

{% highlight cpp %}
  template<typename _Tp>
    class shared_ptr : public __shared_ptr<_Tp>
{% endhighlight %}

第一眼看到这种就没好感，估计又是在外面包的。
<!--more-->

{% highlight cpp %}
      constexpr shared_ptr() noexcept
      : __shared_ptr<_Tp>() { }
      shared_ptr(const shared_ptr&) noexcept = default;

      template<typename _Tp1>
        explicit shared_ptr(_Tp1* __p)
        : __shared_ptr<_Tp>(__p) { }

      template<typename _Tp1, typename _Deleter>
        shared_ptr(_Tp1* __p, _Deleter __d)
        : __shared_ptr<_Tp>(__p, __d) { }

      template<typename _Deleter>
        shared_ptr(nullptr_t __p, _Deleter __d)
        : __shared_ptr<_Tp>(__p, __d) { }
{% endhighlight %}

跟 unqiue\_ptr 基本上走一个路线，后面还有 Alloc 形式的构造，以及 convertible 的构造等等，就不细说了。
operator=(&) 和 operator=(&&) 都借用基类的。

不过，shared\_ptr 和 unique\_ptr 区别很大的一个地方是，unique\_ptr 模板需要接受 deleter 作为模板参数（当然有一个默认的），而给 shared\_ptr 提供 deleter 则是通过构造函数穿参来做的。行为不一致啊！有没有一种隐隐作痛的感觉。这是为什么呢？希望之后可以找到答案。

最后的时候
{% highlight cpp %}
    private:
      // This constructor is non-standard, it is used by allocate_shared.
      template<typename _Alloc, typename... _Args>
        shared_ptr(_Sp_make_shared_tag __tag, const _Alloc& __a,
                   _Args&&... __args)
        : __shared_ptr<_Tp>(__tag, __a, std::forward<_Args>(__args)...)
        { }
      template<typename _Tp1, typename _Alloc, typename... _Args>
        friend shared_ptr<_Tp1>
        allocate_shared(const _Alloc& __a, _Args&&... __args);
      // This constructor is non-standard, it is used by weak_ptr::lock().
      shared_ptr(const weak_ptr<_Tp>& __r, std::nothrow_t)
      : __shared_ptr<_Tp>(__r, std::nothrow) { }
      friend class weak_ptr<_Tp>;
{% endhighlight %}

大概是为 make\_shared, allocate\_shared 和 weak\_ptr 开大门，估计以后用的到。现在先跟到 \_\_share\_ptr 里面一看究竟，为什么要做一层包装呢？

来到 include/bits/shared\_ptr\_base.h
{% highlight cpp %}
  template<typename _Tp, _Lock_policy _Lp = __default_lock_policy>
    class __shared_ptr;
{% endhighlight %}

原来是想封装掉 \_Lock\_policy \_Lp 这个非标准的模板参数。Policy-Based design 的游戏。
咦，这里为什么用到 lock policy 呢？ \_\_shared\_ptr 需要上锁，那么他是线程安全的？

{% highlight cpp %}
    class __shared_ptr
    {
    public:
      typedef _Tp element_type;
      constexpr __shared_ptr() noexcept
      : _M_ptr(0), _M_refcount()
      { }
      template<typename _Tp1>
        explicit __shared_ptr(_Tp1* __p)
        : _M_ptr(__p), _M_refcount(__p)
        {
          __glibcxx_function_requires(_ConvertibleConcept<_Tp1*, _Tp*>)
          static_assert( !is_void<_Tp>::value, "incomplete type" );
          static_assert( sizeof(_Tp1) > 0, "incomplete type" );
          __enable_shared_from_this_helper(_M_refcount, __p, __p);
        }
      template<typename _Tp1, typename _Deleter>
        __shared_ptr(_Tp1* __p, _Deleter __d)
        : _M_ptr(__p), _M_refcount(__p, __d)
        {
          __glibcxx_function_requires(_ConvertibleConcept<_Tp1*, _Tp*>)
          // TODO requires _Deleter CopyConstructible and __d(__p) well-formed
          __enable_shared_from_this_helper(_M_refcount, __p, __p);
        }
{% endhighlight %}

大概可以看得出来，\_\_shared\_ptr 有两个成员，\_M\_ptr, \_M\_refcount。一个是指针一个是垃圾回收用的引用计数。
顺便提一句， \_\_glibcxx\_function\_requires(\_ConvertibleConcept&lt;\_Tp1*, \_Tp*&gt;) 做 convertible concept 检查，之前看到的都是用 enable\_if 来做的，当然都可以达到同样的效果啦（c++ 类库风格都这么不一致你们造嘛，不过贡献太杂乱也就这样吧。。。）。

直接跳到最后看一眼成员好了

{% highlight cpp %}
      _Tp* _M_ptr; // Contained pointer.
      __shared_count<_Lp> _M_refcount; // Reference counter.
{% endhighlight %}

\_\_shared\_count 用到了 lock\_policy 这个模板参数，而且接受 deleter。
回去继续看 \_\_share\_ptr 里面的内容，基本上都是对这两个成员的操作，并没有亮点。
也有帮 make\_shared 做事的，暂时略过。

\_M\_ptr 就是我们封装的指针，\_\_shared\_count 那引用计数是怎样做管理的呢？

{% highlight cpp %}
  template<_Lock_policy _Lp>
    class __shared_count
    {
    public:
      constexpr __shared_count() noexcept : _M_pi(0)
      { }
      template<typename _Ptr>
        explicit
        __shared_count(_Ptr __p) : _M_pi(0)
        {
          __try
            {
              _M_pi = new _Sp_counted_ptr<_Ptr, _Lp>(__p);
            }
          __catch(...)
            {
              delete __p;
              __throw_exception_again;
            }
        }
{% endhighlight %}

\_\_try \_\_catch 在 libsupc++ 中的 exception\_defines.h 可以看到，是一个宏定义，目前可以就把它当成 try。

这竟然又是一层封装，简直惨绝人寰。。。先跳到后面看一下这个成员，还是个指针

{% highlight cpp %}
    private:
      friend class __weak_count<_Lp>;
      _Sp_counted_base<_Lp>* _M_pi;
{% endhighlight %}

lock\_policy 一直传递下去。不过这里何必要 new 呢？等会看一下 \_Sp\_counted\_base 或许可以得到答案。

{% highlight cpp %}
      template<typename _Ptr, typename _Deleter>
        __shared_count(_Ptr __p, _Deleter __d)
        : __shared_count(__p, std::move(__d), allocator<void>())
        { }
      template<typename _Ptr, typename _Deleter, typename _Alloc>
        __shared_count(_Ptr __p, _Deleter __d, _Alloc __a) : _M_pi(0)
        {
          typedef _Sp_counted_deleter<_Ptr, _Deleter, _Alloc, _Lp> _Sp_cd_type;
          typedef typename allocator_traits<_Alloc>::template
            rebind_traits<_Sp_cd_type> _Alloc_traits;
          typename _Alloc_traits::allocator_type __a2(__a);
          _Sp_cd_type* __mem = 0;
          __try
            {
              __mem = _Alloc_traits::allocate(__a2, 1);
              _Alloc_traits::construct(__a2, __mem,
                  __p, std::move(__d), std::move(__a));
              _M_pi = __mem;
            }
          __catch(...)
            {
              __d(__p); // Call _Deleter on __p.
              if (__mem)
                _Alloc_traits::deallocate(__a2, __mem, 1);
              __throw_exception_again;
            }
        }
{% endhighlight %}

\_\_shared\_count 也可以接受 allocator，顺便看一下 allocator 是怎么用的，不过这不是重点。

{% highlight cpp %}
      ~__shared_count() noexcept
      {
        if (_M_pi != nullptr)
          _M_pi->_M_release();
      }
      __shared_count(const __shared_count& __r) noexcept
      : _M_pi(__r._M_pi)
      {
        if (_M_pi != 0)
          _M_pi->_M_add_ref_copy();
      }
      __shared_count&
      operator=(const __shared_count& __r) noexcept
      {
        _Sp_counted_base<_Lp>* __tmp = __r._M_pi;
        if (__tmp != _M_pi)
          {
            if (__tmp != 0)
              __tmp->_M_add_ref_copy();
            if (_M_pi != 0)
              _M_pi->_M_release();
            _M_pi = __tmp;
          }
        return *this;
      }
{% endhighlight %}

自己定义了析构，只是调用  \_M\_pi-&gt;\_M\_release();，看来里面会 delete this（或者是 deleter ）。
拷贝构造函数调用了 \_M\_add\_ref\_copy() 似乎是增加引用计数的地方。
operator= 做了相似的事情，多加了一些判断保证不出“意外”。

回想起operator= 的调用链 share\_ptr -&gt; \_\_shared\_ptr -&gt; \_\_shared\_count。现在我们在最后的 \_\_shared\_count，唯一做正事的 operator=。\_\_shared\_count 只是引用计数的操作者。

\_\_shared\_ptr 持有 \_M\_ptr 供外部访问，\_M\_refcount 供引用计数管理。从一个 shared\_ptr 建立起，到他被各种 copy，构造出其他的 shared\_ptr，这两个对象一直被所有这些 shared\_ptr 共享。于是（开始yy），当 \_M\_refcount 发现引用计数为 0 的时候，就会把自己 delete 掉，从此一个 shared\_ptr 寿终正寝。

注意到 \_\_shared\_count 类模板不带指针类型，而是通过构造函数上的模板构造出相应类型的 \_\_shared\_count。而 \_M\_ptr 和  \_\_shared\_count 里面的指针类型并不一定一样。所以

{% highlight cpp %}
shared_ptr<void> voidptr = shared_ptr<int>(new int(1));
{% endhighlight %}

一样很安全~

{% highlight cpp %}
      void
      _M_swap(__shared_count& __r) noexcept
      {
        _Sp_counted_base<_Lp>* __tmp = __r._M_pi;
        __r._M_pi = _M_pi;
        _M_pi = __tmp;
      }
      long
      _M_get_use_count() const noexcept
      { return _M_pi != 0 ? _M_pi->_M_get_use_count() : 0; }
      bool
      _M_unique() const noexcept
      { return this->_M_get_use_count() == 1; }
      void*
      _M_get_deleter(const std::type_info& __ti) const noexcept
      { return _M_pi ? _M_pi->_M_get_deleter(__ti) : nullptr; }
{% endhighlight %}

后面还有一些代理的函数，把引用计数传到最外面。
注意到 \_\_shared\_count 还有。

{% highlight cpp %}
      // Throw bad_weak_ptr when __r._M_get_use_count() == 0.
      explicit __shared_count(const __weak_count<_Lp>& __r);
      // Does not throw if __r._M_get_use_count() == 0, caller must check.
      explicit __shared_count(const __weak_count<_Lp>& __r, std::nothrow_t);
{% endhighlight %}

具体函数体在类的外面

{% highlight cpp %}
  // Now that __weak_count is defined we can define this constructor:
  template<_Lock_policy _Lp>
    inline
    __shared_count<_Lp>::__shared_count(const __weak_count<_Lp>& __r)
    : _M_pi(__r._M_pi)
    {
      if (_M_pi != nullptr)
        _M_pi->_M_add_ref_lock();
      else
        __throw_bad_weak_ptr();
    }
  // Now that __weak_count is defined we can define this constructor:
  template<_Lock_policy _Lp>
    inline
    __shared_count<_Lp>::
    __shared_count(const __weak_count<_Lp>& __r, std::nothrow_t)
    : _M_pi(__r._M_pi)
    {
      if (_M_pi != nullptr)
        if (!_M_pi->_M_add_ref_lock_nothrow())
          _M_pi = nullptr;
    }
{% endhighlight %}

原来这是帮 weak\_ptr 提升为 shared\_ptr  的方法，也就是从 weak\_ptr 里面的 weak\_count 构造出 shared\_count。
这个过程首先要把 \_\_Sp\_counted\_base  拿过来（所以要指针嘛，这些 shared\_count 和 weak\_count 都要指向一个 count\_base），然后尝试对 \_M\_pi 做引用计数 +1 。

注意到这里有 lock 的字眼，估计 lock\_policy 就在这里，用锁的原因也在这里。
先不管太多，直接进去看一下 \_\_Sp\_counted\_base::\_M\_add\_ref\_lock 

{% highlight cpp %}
  template<>
    inline void
    _Sp_counted_base<_S_single>::
    _M_add_ref_lock()
    {
      if (_M_use_count == 0)
        __throw_bad_weak_ptr();
      ++_M_use_count;
    }
  template<>
    inline void
    _Sp_counted_base<_S_mutex>::
    _M_add_ref_lock()
    {
      __gnu_cxx::__scoped_lock sentry(*this);
      if (__gnu_cxx::__exchange_and_add_dispatch(&_M_use_count, 1) == 0)
        {
          _M_use_count = 0;
          __throw_bad_weak_ptr();
        }
    }

  template<>
    inline void
    _Sp_counted_base<_S_atomic>::
    _M_add_ref_lock()
    {
      // Perform lock-free add-if-not-zero operation.
      _Atomic_word __count = _M_get_use_count();
      do
        {
          if (__count == 0)
            __throw_bad_weak_ptr();
          // Replace the current counter value with the old value + 1, as
          // long as it's not changed meanwhile.
        }
      while (!__atomic_compare_exchange_n(&_M_use_count, &__count, __count + 1,
                                          true, __ATOMIC_ACQ_REL,
                                          __ATOMIC_RELAXED));
    }
{% endhighlight %}

可以看到，一共有三种 lock\_policy。
在 include/ext/concurrence.h 中

{% highlight cpp %}
  // Available locking policies:
  // _S_single single-threaded code that doesn't need to be locked.
  // _S_mutex multi-threaded code that requires additional support
  // from gthr.h or abstraction layers in concurrence.h.
  // _S_atomic multi-threaded code using atomic operations.
  enum _Lock_policy { _S_single, _S_mutex, _S_atomic };
  // Compile time constant that indicates prefered locking policy in
  // the current configuration.
  static const _Lock_policy __default_lock_policy =
#ifdef __GTHREADS
#if (defined(__GCC_HAVE_SYNC_COMPARE_AND_SWAP_2) \
     && defined(__GCC_HAVE_SYNC_COMPARE_AND_SWAP_4))
  _S_atomic;
#else
  _S_mutex;
#endif
#else
  _S_single;
#endif
{% endhighlight %}

我们现在在什么样的 default lock policy 环境下呢？ \_\_GTHREADS 是 libgcc 中的 gthread 存在性检测，gthread 是 gcc 中类似 pthread 一样的东西，为上面各种线程工具提供抽象层。后面里面的两个则是 gcc 自定义宏，和具体机器架构有关。
不妨直接把 \_\_default\_lock\_policy 来看一下现在是什么情况。在我这里（gcc 4.9, x86\_64) 是 \_S\_atomic。

\_M\_add\_ref\_lock 就是在做下面的事情
{% highlight cpp %}
  template<>
    inline void
    _Sp_counted_base<_S_atomic>::
    _M_add_ref_lock()
    {
      // Perform lock-free add-if-not-zero operation.
      _Atomic_word __count = _M_get_use_count();
      do
        {
          if (__count == 0)
            __throw_bad_weak_ptr();
          // Replace the current counter value with the old value + 1, as
          // long as it's not changed meanwhile.
        }
      while (!__atomic_compare_exchange_n(&_M_use_count, &__count, __count + 1,
                                          true, __ATOMIC_ACQ_REL,
                                          __ATOMIC_RELAXED));
    }
{% endhighlight %}

\_Atomic\_word 的定义在 config/cpu/generic/atomic\_word.h （我相信你也是 generic），

{% highlight cpp %}
typedef int _Atomic_word;
{% endhighlight %}

\_\_atomic\_compare\_exchange\_n 是 gcc build-in 的原子操作之一 http://gcc.gnu.org/onlinedocs/gcc/\_005f\_005fatomic-Builtins.html 。我们先不纠结于 atomic 操作和各种内存模型，反正这个 add\_ref\_lock 是对 ref count 是原子操作。

咦，既然 add\_ref 都要原子，那析构的时候也是要原子了，否则 ref count 不就乱套了。

{% highlight cpp %}
      void
      _M_release() noexcept
      {
        // Be race-detector-friendly. For more info see bits/c++config.
        _GLIBCXX_SYNCHRONIZATION_HAPPENS_BEFORE(&_M_use_count);
        if (__gnu_cxx::__exchange_and_add_dispatch(&_M_use_count, -1) == 1)
          {
            _GLIBCXX_SYNCHRONIZATION_HAPPENS_AFTER(&_M_use_count);
            _M_dispose();
            // There must be a memory barrier between dispose() and destroy()
            // to ensure that the effects of dispose() are observed in the
            // thread that runs destroy().
            // See http://gcc.gnu.org/ml/libstdc++/2005-11/msg00136.html
            if (_Mutex_base<_Lp>::_S_need_barriers)
              {
                _GLIBCXX_READ_MEM_BARRIER;
                _GLIBCXX_WRITE_MEM_BARRIER;
              }
            // Be race-detector-friendly. For more info see bits/c++config.
            _GLIBCXX_SYNCHRONIZATION_HAPPENS_BEFORE(&_M_weak_count);
            if (__gnu_cxx::__exchange_and_add_dispatch(&_M_weak_count,
                                                       -1) == 1)
              {
                _GLIBCXX_SYNCHRONIZATION_HAPPENS_AFTER(&_M_weak_count);
                _M_destroy();
              }
          }
      }
{% endhighlight %}

似乎混入了奇奇怪怪的东西，我们忽略 \_GLIBCXX\_SYNCHRONIZATION\_HAPPENS\_BEFORE， \_GLIBCXX\_SYNCHRONIZATION\_HAPPENS\_AFTER 这些需要 race detector 支持的宏（比如说 code.google.com/p/data-race-test/）。
\_\_exchange\_and\_add\_dispatch 在 include/ext/atomicity.h 中，暂时不理，反正我们知道这是在做 exchange\_and\_add 这个原子操作。

{% highlight cpp %}
{ tmp = *ptr; *ptr += val; return tmp; }
{% endhighlight %}

在 \_M\_use\_count-- == 1 的情况下进行 \_M\_dispose()，进而若 \_M\_weak\_count-- == 1 时，进行 \_M\_destroy()
原来有两个计数。

{% highlight cpp %}
      // Called when _M_use_count drops to zero, to release the resources
      // managed by *this.
      virtual void
      _M_dispose() noexcept = 0;
      // Called when _M_weak_count drops to zero.
      virtual void
      _M_destroy() noexcept
      { delete this; }
{% endhighlight %}
原来 weak\_count 减到 0 才会真正的销毁这个对象（所有持有 shared\_ptr 都没了），那 \_M\_dispose 又是闹哪样，似乎有很多子类的样子。而对于 \_\_shared\_count 来说，在上面的构造函数里面，看到 new 出来的是 \_Sp\_counted\_ptr 。

{% highlight cpp %}
  // Counted ptr with no deleter or allocator support
  template<typename _Ptr, _Lock_policy _Lp>
    class _Sp_counted_ptr final : public _Sp_counted_base<_Lp>

  // Support for custom deleter and/or allocator
  template<typename _Ptr, typename _Deleter, typename _Alloc, _Lock_policy _Lp>
    class _Sp_counted_deleter final : public _Sp_counted_base<_Lp>

  // helpers for make_shared / allocate_shared
  template<typename _Tp, typename _Alloc, _Lock_policy _Lp>
    class _Sp_counted_ptr_inplace final : public _Sp_counted_base<_Lp>
{% endhighlight %}

原来有这几种情况，我们先来看最基本的 \_Sp\_counted\_ptr 

{% highlight cpp %}
  // Counted ptr with no deleter or allocator support
  template<typename _Ptr, _Lock_policy _Lp>
    class _Sp_counted_ptr final : public _Sp_counted_base<_Lp>
    {
    public:
      explicit
      _Sp_counted_ptr(_Ptr __p) noexcept
      : _M_ptr(__p) { }
      virtual void
      _M_dispose() noexcept
      { delete _M_ptr; }
      virtual void
      _M_destroy() noexcept
      { delete this; }
      virtual void*
      _M_get_deleter(const std::type_info&) noexcept
      { return nullptr; }
      _Sp_counted_ptr(const _Sp_counted_ptr&) = delete;
      _Sp_counted_ptr& operator=(const _Sp_counted_ptr&) = delete;
    private:
      _Ptr _M_ptr;
    };
  template<>
    inline void
    _Sp_counted_ptr<nullptr_t, _S_single>::_M_dispose() noexcept { }
  template<>
    inline void
    _Sp_counted_ptr<nullptr_t, _S_mutex>::_M_dispose() noexcept { }
  template<>
    inline void
    _Sp_counted_ptr<nullptr_t, _S_atomic>::_M_dispose() noexcept { }
{% endhighlight %}

用 \_Ptr \_\_p 构造，\_M\_dispose 是 delete \_M\_ptr 销毁 shared\_ptr 管理的那个对象，\_M\_destroy 是 delete this，销毁 \_Sp\_counted\_base 这个计数用的对象。

复习一下之前的逻辑，在 \_M\_use\_count-- == 1 的情况下进行 \_M\_dispose()，进而若 \_M\_weak\_count-- == 1 时，进行 \_M\_destroy()。对象可能都没了，但是可能有 weak\_ptr 引用，而此时的 weak\_ptr 是无法提升为 shared\_ptr 的。这两个计数大概就是  shared\_ptr 和 weak\_ptr 的原理吧，我们继续验证。

继承的 \_Sp\_counted\_ptr 看过了，我们回过来看 base class，\_Sp\_counted\_base

{% highlight cpp %}
  template<_Lock_policy _Lp = __default_lock_policy>
    class _Sp_counted_base
    : public _Mutex_base<_Lp>
{% endhighlight %}

又继承了 \_Mutex\_base。根据 \_Lock\_policy 确定 \_S\_need\_barriers， \_S\_need\_barriers 是在 \_M\_release 中需要的。
不过 \_S\_need\_barriers 只在 \_S\_mutex 情况下为 1（代码就懒得贴了)，而我们现在是 \_S\_atomic，所以可以暂时无视他。

{% highlight cpp %}
      void
      _M_add_ref_copy()
      { __gnu_cxx::__atomic_add_dispatch(&_M_use_count, 1); }

      void
      _M_weak_add_ref() noexcept
      { __gnu_cxx::__atomic_add_dispatch(&_M_weak_count, 1); }
{% endhighlight %}

add\_ref\_copy，weak\_add\_ref 也是原子操作。

{% highlight cpp %}
      void
      _M_weak_release() noexcept
      {
        // Be race-detector-friendly. For more info see bits/c++config.
        _GLIBCXX_SYNCHRONIZATION_HAPPENS_BEFORE(&_M_weak_count);
        if (__gnu_cxx::__exchange_and_add_dispatch(&_M_weak_count, -1) == 1)
          {
            _GLIBCXX_SYNCHRONIZATION_HAPPENS_AFTER(&_M_weak_count);
            if (_Mutex_base<_Lp>::_S_need_barriers)
              {
                // See _M_release(),
                // destroy() must observe results of dispose()
                _GLIBCXX_READ_MEM_BARRIER;
                _GLIBCXX_WRITE_MEM_BARRIER;
              }
            _M_destroy();
          }
      }
{% endhighlight %}

\_M\_weak\_release 的逻辑和 \_M\_release 的后半段相同。看到这里，难道 shared\_ptr 和 weak\_ptr 里面的 counter\_base 都是这一个东西？

{% highlight cpp %}
      long
      _M_get_use_count() const noexcept
      {
        // No memory barrier is used here so there is no synchronization
        // with other threads.
        return __atomic_load_n(&_M_use_count, __ATOMIC_RELAXED);
      }
{% endhighlight %}

恩还有 get\_use\_count 。不过没有 get\_weak\_count，这个也没啥用其实~

当然还有两个成员，就是之前一直在说的两个计数

{% highlight cpp %}
      _Atomic_word _M_use_count; // #shared
      _Atomic_word _M_weak_count; // #weak + (#shared != 0)
{% endhighlight %}

看到这里，shared\_ptr 的基本逻辑已经出来了。在 operator=, copy ctor 等情况下调用 add\_ref\_count，销毁时候调用 \_M\_release 。而最后一个销毁的发现 count 已经是 0 了，便会把持有的对象 ptr 再销毁。
shared\_ptr 的引用计数都是原子操作，operator=, copy ctor 等是线程安全的，或者是说读都是线程安全的。但是 \_\_shared\_ptr 里面实际是 ptr, 和 counter 两个对象，所以对 shared\_ptr 不是线程安全的。

在忽略 deleter 和 allocator 的情况下，shared\_ptr 也就这样了。刚才一直遇到 weak，我们来看看 weak 是怎样的~~

跟 shared\_ptr 基本相似
{% highlight cpp %}
  template<typename _Tp>
    class weak_ptr : public __weak_ptr<_Tp>
{% endhighlight %}

{% highlight cpp %}
      constexpr __weak_ptr() noexcept
      : _M_ptr(0), _M_refcount()
      { }
      __weak_ptr(const __weak_ptr&) noexcept = default;
      __weak_ptr& operator=(const __weak_ptr&) noexcept = default;
      ~__weak_ptr() = default;
{% endhighlight %}

{% highlight cpp %}
      template<typename _Tp1, typename = typename
               std::enable_if<std::is_convertible<_Tp1*, _Tp*>::value>::type>
        __weak_ptr(const __weak_ptr<_Tp1, _Lp>& __r) noexcept
        : _M_refcount(__r._M_refcount)
        { _M_ptr = __r.lock().get(); }
      template<typename _Tp1, typename = typename
               std::enable_if<std::is_convertible<_Tp1*, _Tp*>::value>::type>
        __weak_ptr(const __shared_ptr<_Tp1, _Lp>& __r) noexcept
        : _M_ptr(__r._M_ptr), _M_refcount(__r._M_refcount)
        { }
      template<typename _Tp1>
        __weak_ptr&
        operator=(const __weak_ptr<_Tp1, _Lp>& __r) noexcept
        {
          _M_ptr = __r.lock().get();
          _M_refcount = __r._M_refcount;
          return *this;
        }
      template<typename _Tp1>
        __weak_ptr&
        operator=(const __shared_ptr<_Tp1, _Lp>& __r) noexcept
        {
          _M_ptr = __r._M_ptr;
          _M_refcount = __r._M_refcount;
          return *this;
        }
{% endhighlight %}

注意到从 \_\_weak\_ptr 到 \_\_weak\_ptr，必须要做 lock 再拿 ptr，原因就是拿到的 ptr 可能随时都被别人析构掉，而拿到了 invalid 的指针。虽说 \_\_weak\_ptr 拿到一个 invalid ptr 并没有什么问题，不过当 \_Tp1 和 \_Lp 是虚继承关系时，\_M\_ptr = \_\_r.\_M\_ptr; 这样的转换会对齐内容进行访问（virtual inheritance 奇妙的 mem layout）。

不过一路上基本也跟 \_\_shared\_ptr 差不多，都转发给了 \_M\_ptr 和 \_M\_refcount。

{% highlight cpp %}
      _Tp* _M_ptr; // Contained pointer.
      __weak_count<_Lp> _M_refcount; // Reference counter.
{% endhighlight %}

来看 lock
{% highlight cpp %}
      __shared_ptr<_Tp, _Lp>
      lock() const noexcept
      { return __shared_ptr<element_type, _Lp>(*this, std::nothrow); }
{% endhighlight %}

直接调 \_\_shared\_ptr 构造啊。。。。

{% highlight cpp %}
      // This constructor is used by __weak_ptr::lock() and
      // shared_ptr::shared_ptr(const weak_ptr&, std::nothrow_t).
      __shared_ptr(const __weak_ptr<_Tp, _Lp>& __r, std::nothrow_t)
      : _M_refcount(__r._M_refcount, std::nothrow)
      {
        _M_ptr = _M_refcount._M_get_use_count() ? __r._M_ptr : nullptr;
      }
{% endhighlight %}

关键在从 \_weak\_count 里面构造出 \_shared\_count 的过程。而这个过程上面有看到过，就是判断是否为 nullptr 之后做 \_M\_add\_ref\_lock() 增加计数。

诶，似乎一直没有看到 weak\_count 那个计数增长的踪影。让我们来看 \_\_weak\_count。
其实和 \_\_shared\_count 大同小异，不同就是这里的 copy ctor, operator= 增加的是 weak\_ref

{% highlight cpp %}
  template<_Lock_policy _Lp>
    class __weak_count
    {
    public:
      constexpr __weak_count() noexcept : _M_pi(0)
      { }
      __weak_count(const __shared_count<_Lp>& __r) noexcept
      : _M_pi(__r._M_pi)
      {
        if (_M_pi != 0)
          _M_pi->_M_weak_add_ref();
      }
      __weak_count(const __weak_count<_Lp>& __r) noexcept
      : _M_pi(__r._M_pi)
      {
        if (_M_pi != 0)
          _M_pi->_M_weak_add_ref();
      }
      ~__weak_count() noexcept
      {
        if (_M_pi != 0)
          _M_pi->_M_weak_release();
      }

      __weak_count<_Lp>&
      operator=(const __shared_count<_Lp>& __r) noexcept
      {
        _Sp_counted_base<_Lp>* __tmp = __r._M_pi;
        if (__tmp != 0)
          __tmp->_M_weak_add_ref();
        if (_M_pi != 0)
          _M_pi->_M_weak_release();
        _M_pi = __tmp;
        return *this;
      }
      __weak_count<_Lp>&
      operator=(const __weak_count<_Lp>& __r) noexcept
      {
        _Sp_counted_base<_Lp>* __tmp = __r._M_pi;
        if (__tmp != 0)
          __tmp->_M_weak_add_ref();
        if (_M_pi != 0)
          _M_pi->_M_weak_release();
        _M_pi = __tmp;
        return *this;
      }
{% endhighlight %}

而最后发现，他也是在用 \_Sp\_counted\_base。
{% highlight cpp %}
 _Sp_counted_base<_Lp>* _M_pi;
{% endhighlight %}

但发现 \_\_weak\_count 的构造函数里面并没有 new 出一个 \_Sp\_counted。原来 weak\_ptr 只能从 shared\_ptr 那边拿这个 \_Sp\_counted\_base，所有指向同一个对象的 weak\_ptr 和 shared\_ptr 都共享这个 \_Sp\_counted\_base。
到此，weak\_ptr 和 shared\_ptr 的原理已经明了了。

当然，shared\_ptr 周边还有配套的基础设施，比如

{% highlight cpp %}
  // 20.7.2.2.9 shared_ptr casts.
  template<typename _Tp, typename _Tp1>
    inline shared_ptr<_Tp>
    static_pointer_cast(const shared_ptr<_Tp1>& __r) noexcept
    { return shared_ptr<_Tp>(__r, static_cast<_Tp*>(__r.get())); }
  template<typename _Tp, typename _Tp1>
    inline shared_ptr<_Tp>
    const_pointer_cast(const shared_ptr<_Tp1>& __r) noexcept
    { return shared_ptr<_Tp>(__r, const_cast<_Tp*>(__r.get())); }
  template<typename _Tp, typename _Tp1>
    inline shared_ptr<_Tp>
    dynamic_pointer_cast(const shared_ptr<_Tp1>& __r) noexcept
    {
      if (_Tp* __p = dynamic_cast<_Tp*>(__r.get()))
        return shared_ptr<_Tp>(__r, __p);
      return shared_ptr<_Tp>();
    }
{% endhighlight %}

make\_shared\_from\_this 之前有用过。注意到 \_\_shared\_ptr 的构造函数里面每次都会调用一次 \_\_enable\_shared\_from\_this\_helper，这个应该指引了方向。

{% highlight cpp %}
  // Friend of __enable_shared_from_this.
  template<_Lock_policy _Lp, typename _Tp1, typename _Tp2>
    void
    __enable_shared_from_this_helper(const __shared_count<_Lp>&,
                                     const __enable_shared_from_this<_Tp1,
                                     _Lp>*, const _Tp2*) noexcept;
  // Friend of enable_shared_from_this.
  template<typename _Tp1, typename _Tp2>
    void
    __enable_shared_from_this_helper(const __shared_count<>&,
                                     const enable_shared_from_this<_Tp1>*,
                                     const _Tp2*) noexcept;
  template<_Lock_policy _Lp>
    inline void
    __enable_shared_from_this_helper(const __shared_count<_Lp>&, ...) noexcept
    { }
{% endhighlight %}

分别对应 \_\_enable\_shared\_from\_this\_helper 和 enable\_shared\_from\_this\_helper 里面的 friend 函数。为啥有两个呢？。。。

看一下，唯一不同的就是 \_\_enable\_shared\_from\_this\_helper 上面带着 lock\_policy 模板参数。（大哥你也不用这样吧。。）

{% highlight cpp %}
  template<typename _Tp>
    class enable_shared_from_this
    {
    protected:
      constexpr enable_shared_from_this() noexcept { }
      enable_shared_from_this(const enable_shared_from_this&) noexcept { }
      enable_shared_from_this&
      operator=(const enable_shared_from_this&) noexcept
      { return *this; }
      ~enable_shared_from_this() { }
    public:
      shared_ptr<_Tp>
      shared_from_this()
      { return shared_ptr<_Tp>(this->_M_weak_this); }
      shared_ptr<const _Tp>
      shared_from_this() const
      { return shared_ptr<const _Tp>(this->_M_weak_this); }
    private:
      template<typename _Tp1>
        void
        _M_weak_assign(_Tp1* __p, const __shared_count<>& __n) const noexcept
        { _M_weak_this._M_assign(__p, __n); }
      template<typename _Tp1>
        friend void
        __enable_shared_from_this_helper(const __shared_count<>& __pn,
                                         const enable_shared_from_this* __pe,
                                         const _Tp1* __px) noexcept
        {
          if (__pe != 0)
            __pe->_M_weak_assign(const_cast<_Tp1*>(__px), __pn);
        }
      mutable weak_ptr<_Tp> _M_weak_this;
    };
{% endhighlight %}

{% highlight cpp %}
      void
      _M_assign(_Tp* __ptr, const __shared_count<_Lp>& __refcount) noexcept
      {
        _M_ptr = __ptr;
        _M_refcount = __refcount;
      }
{% endhighlight %}

\_M\_assign 就平淡无奇了。总之我们需要在 shared\_ptr 构造的时候把他的 ptr 和 refcount 拿到手，构成自己的 weak\_ptr，让之后的 shared\_from\_this 来用。那为啥这里持有 weak 不是 shared 。。你想想，这里持有 shared 的话不就循环引用了。。。。

原来是通过持有一个 weak\_ptr 来实现 shared from this。
还有我一直比较关心 make\_shared，make\_shared 比正常搞 shared\_ptr 有一个优点就是他会把 \_Sp\_counted\_base 和 对象 的内存挨在一起分配，一定程度上减少了内存碎片。

{% highlight cpp %}
  template<typename _Tp, typename... _Args>
    inline shared_ptr<_Tp>
    make_shared(_Args&&... __args)
    {
      typedef typename std::remove_const<_Tp>::type _Tp_nc;
      return std::allocate_shared<_Tp>(std::allocator<_Tp_nc>(),
                                       std::forward<_Args>(__args)...);
    }
{% endhighlight %}

这个变态又去转给了 allocate\_shared。allocate\_shared 就是用 allocator 的 make\_shared，而这里我们用了 std::allocator，其实里面就是 new 和 delete 啦。

{% highlight cpp %}
  template<typename _Tp, typename _Alloc, typename... _Args>
    inline shared_ptr<_Tp>
    allocate_shared(const _Alloc& __a, _Args&&... __args)
    {
      return shared_ptr<_Tp>(_Sp_make_shared_tag(), __a,
                             std::forward<_Args>(__args)...);
    }
{% endhighlight %}

看来我们要回过头来看 share\_ptr 带 allocate\_tag 的构造了。

{% highlight cpp %}
    private:
      // This constructor is non-standard, it is used by allocate_shared.
      template<typename _Alloc, typename... _Args>
        shared_ptr(_Sp_make_shared_tag __tag, const _Alloc& __a,
                   _Args&&... __args)
        : __shared_ptr<_Tp>(__tag, __a, std::forward<_Args>(__args)...)
        { }

      template<typename _Tp1, typename _Alloc, typename... _Args>
        friend shared_ptr<_Tp1>
        allocate_shared(const _Alloc& __a, _Args&&... __args);
{% endhighlight %}

继续转发。

{% highlight cpp %}
#ifdef __GXX_RTTI
    protected:
      // This constructor is non-standard, it is used by allocate_shared.
      template<typename _Alloc, typename... _Args>
        __shared_ptr(_Sp_make_shared_tag __tag, const _Alloc& __a,
                     _Args&&... __args)
        : _M_ptr(), _M_refcount(__tag, (_Tp*)0, __a,
                                std::forward<_Args>(__args)...)
        {
          // _M_ptr needs to point to the newly constructed object.
          // This relies on _Sp_counted_ptr_inplace::_M_get_deleter.
          void* __p = _M_refcount._M_get_deleter(typeid(__tag));
          _M_ptr = static_cast<_Tp*>(__p);
          __enable_shared_from_this_helper(_M_refcount, _M_ptr, _M_ptr);
        }
#else
{% endhighlight %}

先看  \_M\_refcount 的构造

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

WTF 。。。之前一直在避免 alloc 想让问题简单化。。。。今天就烂尾到这里好了，找时间再把 allocate 解决掉。