---
layout: post
title: "containers，std::vector"
description: ""
category: C++
tags: [C++, STL, code reading]
---
{% include JB/setup %}
vector 是最最最最最喜闻乐见没有之一的容器了。然后，由于众所周知的原因，略过 vector&lt;bool&gt;

gcc 家的 stl 除了提供了基本的 container，还给了配套的 [debug](http://gcc.gnu.org/onlinedocs/gcc-4.7.1/libstdc++/manual/manual/debug_mode.html) 和 [profile](http://gcc.gnu.org/onlinedocs/gcc-4.7.1/libstdc++/manual/manual/profile_mode.html) 设施。

另外一些算法还提供了 parallel mode。

不过话说回来，感觉 debug mode 和 profile mode 都很积累。debug 报不出行号，内存泄露似乎还是 valgrind 和 tcmalloc 跑起来比较舒服，越界访问直接 gdb 就能定位到行。profile 会给出建议或者性能表现的特性，还是不如直接上 perf 或者 vtune。。。。不过有空还是可以去研究一下内部的原理。

include/bits/vector
{% highlight cpp %}
  template<typename _Tp, typename _Alloc = std::allocator<_Tp> >
    class vector : protected _Vector_base<_Tp, _Alloc>
{% endhighlight %}
<!--more-->

用了 protected 继承，应该是不想在 \_Vector\_base 里面写 protected。protected 和 private 继承的公用基本一样，都用来做 implementation inheritance。不过 protected 继承还会把 base 里面的成员暴露给子子孙孙，方便大家使用。

{% highlight cpp %}
  /// See bits/stl_deque.h's _Deque_base for an explanation.
  template<typename _Tp, typename _Alloc>
    struct _Vector_base
    {
      typedef typename __gnu_cxx::__alloc_traits<_Alloc>::template
        rebind<_Tp>::other _Tp_alloc_type;
      typedef typename __gnu_cxx::__alloc_traits<_Tp_alloc_type>::pointer
        pointer;
{% endhighlight %}

这里的 rebind 和 pointer 在之前 allocator 的内容中都见过。好的，那去看一下 stl\_deque.h 里面的注释。
{% highlight cpp %}
  /**
   * Deque base class. This class provides the unified face for %deque's
   * allocation. This class's constructor and destructor allocate and
   * deallocate (but do not initialize) storage. This makes %exception
   * safety easier.
   *
   * Nothing in this class ever constructs or destroys an actual Tp element.
   * (Deque handles that itself.) Only/All memory management is performed
   * here.
  */
{% endhighlight %}

\_Vector\_base 是一个内存管理用具，而且只做内存管理。其中有一个 \_Vector\_impl 成员
{% highlight cpp %}
    public:
      _Vector_impl _M_impl;
{% endhighlight %}

{% highlight cpp %}
      struct _Vector_impl
      : public _Tp_alloc_type
      {
        pointer _M_start;
        pointer _M_finish;
        pointer _M_end_of_storage;
        _Vector_impl()
        : _Tp_alloc_type(), _M_start(), _M_finish(), _M_end_of_storage()
        { }
        _Vector_impl(_Tp_alloc_type const& __a) _GLIBCXX_NOEXCEPT
        : _Tp_alloc_type(__a), _M_start(), _M_finish(), _M_end_of_storage()
        { }
#if __cplusplus >= 201103L
        _Vector_impl(_Tp_alloc_type&& __a) noexcept
        : _Tp_alloc_type(std::move(__a)),
          _M_start(), _M_finish(), _M_end_of_storage()
        { }
#endif
        void _M_swap_data(_Vector_impl& __x) _GLIBCXX_NOEXCEPT
        {
          std::swap(_M_start, __x._M_start);
          std::swap(_M_finish, __x._M_finish);
          std::swap(_M_end_of_storage, __x._M_end_of_storage);
        }
      };
{% endhighlight %}

原来是持有 \_M\_start， \_M\_finish，\_M\_end\_of\_storage 三个指针。分别应该对应元素起始，元素末尾，和内存末尾（内存是会多分配的）。而且继承了 allocator 。

\_Vector\_base 里面自然会有 get\_allocator 什么的
{% highlight cpp %}
    public:
      typedef _Alloc allocator_type;
      _Tp_alloc_type&
      _M_get_Tp_allocator() _GLIBCXX_NOEXCEPT
      { return *static_cast<_Tp_alloc_type*>(&this->_M_impl); }
      const _Tp_alloc_type&
      _M_get_Tp_allocator() const _GLIBCXX_NOEXCEPT
      { return *static_cast<const _Tp_alloc_type*>(&this->_M_impl); }
      allocator_type
      get_allocator() const _GLIBCXX_NOEXCEPT
      { return allocator_type(_M_get_Tp_allocator()); }
{% endhighlight %}

构造函数
{% highlight cpp %}
      _Vector_base()
      : _M_impl() { }
      _Vector_base(const allocator_type& __a) _GLIBCXX_NOEXCEPT
      : _M_impl(__a) { }
      _Vector_base(size_t __n)
      : _M_impl()
      { _M_create_storage(__n); }
      _Vector_base(size_t __n, const allocator_type& __a)
      : _M_impl(__a)
      { _M_create_storage(__n); }
{% endhighlight %}

看来 \_M\_create\_storage 是分配内存的地方，接下来还有右值构造。

{% highlight cpp %}
      _Vector_base(_Tp_alloc_type&& __a) noexcept
      : _M_impl(std::move(__a)) { }
      _Vector_base(_Vector_base&& __x) noexcept
      : _M_impl(std::move(__x._M_get_Tp_allocator()))
      { this->_M_impl._M_swap_data(__x._M_impl); }
      _Vector_base(_Vector_base&& __x, const allocator_type& __a)
      : _M_impl(__a)
      {
        if (__x.get_allocator() == __a)
          this->_M_impl._M_swap_data(__x._M_impl);
        else
          {
            size_t __n = __x._M_impl._M_finish - __x._M_impl._M_start;
            _M_create_storage(__n);
          }
      }
{% endhighlight %}

析构的时候调用 deallocate
{% highlight cpp %}
      ~_Vector_base() _GLIBCXX_NOEXCEPT
      { _M_deallocate(this->_M_impl._M_start, this->_M_impl._M_end_of_storage
                      - this->_M_impl._M_start); }
{% endhighlight %}

那么 \_M\_deallocate 就应该是用 allocate\_trait 来做释放

{% highlight cpp %}
      void
      _M_deallocate(pointer __p, size_t __n)
      {
        typedef __gnu_cxx::__alloc_traits<_Tp_alloc_type> _Tr;
        if (__p)
          _Tr::deallocate(_M_impl, __p, __n);
      }
{% endhighlight %}

相应的还有一个 \_M\_allocate，不过之前调的都是 \_M\_create\_storage

{% highlight cpp %}
    private:
      void
      _M_create_storage(size_t __n)
      {
        this->_M_impl._M_start = this->_M_allocate(__n);
        this->_M_impl._M_finish = this->_M_impl._M_start;
        this->_M_impl._M_end_of_storage = this->_M_impl._M_start + __n;
      }
{% endhighlight %}

\_Vector\_base 的结构非常简单。我们回到 vector。vector 会用到 \_Vector\_base 里面很多东西~

{% highlight cpp %}
      typedef _Vector_base<_Tp, _Alloc> _Base;
      typedef typename _Base::_Tp_alloc_type _Tp_alloc_type;
      typedef __gnu_cxx::__alloc_traits<_Tp_alloc_type> _Alloc_traits;

    public:
      typedef _Tp value_type;
      typedef typename _Base::pointer pointer;
      typedef typename _Alloc_traits::const_pointer const_pointer;
      typedef typename _Alloc_traits::reference reference;
      typedef typename _Alloc_traits::const_reference const_reference;
      typedef __gnu_cxx::__normal_iterator<pointer, vector> iterator;
      typedef __gnu_cxx::__normal_iterator<const_pointer, vector>
      const_iterator;
      typedef std::reverse_iterator<const_iterator> const_reverse_iterator;
      typedef std::reverse_iterator<iterator> reverse_iterator;
      typedef size_t size_type;
      typedef ptrdiff_t difference_type;
      typedef _Alloc allocator_type;
{% endhighlight %}

注意到，我们这里无论是定义 pointer 还是 reference 都是跟从 allocator 中的 type。不过标准里 value\_type, reference 这些定义是按照 typename \_Tp 定义的，pointer 是跟随 allocator 定义的。whatever，反正 STL 中的 vector 是要       \_\_glibcxx\_class\_requires2(\_Tp, \_Alloc\_value\_type, \_SameTypeConcept) 。

{% highlight cpp %}
    protected:
      using _Base::_M_allocate;
      using _Base::_M_deallocate;
      using _Base::_M_impl;
      using _Base::_M_get_Tp_allocator; 
{% endhighlight %}
vector 会用到这些做内存管理。

接下来是构造函数，略过 trivial 的。
{% highlight cpp %}
      explicit
      vector(size_type __n, const allocator_type& __a = allocator_type())
      : _Base(__n, __a)
      { _M_default_initialize(__n); }
{% endhighlight %}

分配之后，交给了 \_M\_default\_initialize 做初始化。

{% highlight cpp %}
#if __cplusplus >= 201103L
      // Called by the vector(n) constructor.
      void
      _M_default_initialize(size_type __n)
      {
        std::__uninitialized_default_n_a(this->_M_impl._M_start, __n,
                                         _M_get_Tp_allocator());
        this->_M_impl._M_finish = this->_M_impl._M_end_of_storage;
      }
#endif
{% endhighlight %}

在 include/bits/stl\_uninitialized.h 中
{% highlight cpp %}
  template<typename _ForwardIterator, typename _Size, typename _Allocator>
    void
    __uninitialized_default_n_a(_ForwardIterator __first, _Size __n,
                                _Allocator& __alloc)
    {
      _ForwardIterator __cur = __first;
      __try
        {
          typedef __gnu_cxx::__alloc_traits<_Allocator> __traits;
          for (; __n > 0; --__n, ++__cur)
            __traits::construct(__alloc, std::__addressof(*__cur));
        }
      __catch(...)
        {
          std::_Destroy(__first, __cur, __alloc);
          __throw_exception_again;
        }
    }
{% endhighlight %}

囧rz。原来是跳进来继续用 allocator 的 construct。何必呢。如果构造失败的话，则会 std::\_Destroy

{% highlight cpp %}
  /**
   * Destroy a range of objects. If the value_type of the object has
   * a trivial destructor, the compiler should optimize all of this
   * away, otherwise the objects' destructors must be invoked.
   */
  template<typename _ForwardIterator>
    inline void
    _Destroy(_ForwardIterator __first, _ForwardIterator __last)
    {
      typedef typename iterator_traits<_ForwardIterator>::value_type
                       _Value_type;
      std::_Destroy_aux<__has_trivial_destructor(_Value_type)>::
        __destroy(__first, __last);
    }
{% endhighlight %}

原来是想多做点优化，如果是 trivial destructor 的话，干脆就略过了。std::\_Destroy\_aux 还是模板的辅助工具

{% highlight cpp %}
  template<bool>
    struct _Destroy_aux
    {
      template<typename _ForwardIterator>
        static void
        __destroy(_ForwardIterator __first, _ForwardIterator __last)
        {
          for (; __first != __last; ++__first)
            std::_Destroy(std::__addressof(*__first));
        }
    };
  template<>
    struct _Destroy_aux<true>
    {
      template<typename _ForwardIterator>
        static void
        __destroy(_ForwardIterator, _ForwardIterator) { }
    };
{% endhighlight %}

不过我比较关心的是，什么情况下算是 trivial destructor。
{% highlight cpp %}
The implicitly-declared destructor for class T is trivial if all of the following is true:


1. The destructor is not virtual (that is, the base class destructor is not virtual)
2. All direct base classes have trivial destructors
3. All non-static data members of class type (or array of class type) have trivial destructors

A trivial destructor is a destructor that performs no action. Objects with trivial destructors don't require a delete-expression and may be disposed of by simply deallocating their storage. All data types compatible with the C language (POD types) are trivially destructible.
{% endhighlight %}

酱紫。那继续下去。

{% highlight cpp %}
      vector(size_type __n, const value_type& __value,
             const allocator_type& __a = allocator_type())
      : _Base(__n, __a)
      { _M_fill_initialize(__n, __value); }
{% endhighlight %}
这个应该跟之前的原理差不多，接着看。

{% highlight cpp %}
      vector(const vector& __x)
      : _Base(__x.size(),
        _Alloc_traits::_S_select_on_copy(__x._M_get_Tp_allocator()))
      { this->_M_impl._M_finish =
          std::__uninitialized_copy_a(__x.begin(), __x.end(),
                                      this->_M_impl._M_start,
                                      _M_get_Tp_allocator());
      }
{% endhighlight %}

咦，这个 \_S\_select\_on\_copy 之前没有看过。找 alloc\_traits 里面竟然没有。。
在 \_\_alloc\_trait 里面 include/ext/alloc\_traits.h

{% highlight cpp %}
template<typename _Alloc>
  struct __alloc_traits
#if __cplusplus >= 201103L
  : std::allocator_traits<_Alloc>
#endif
{% endhighlight %}

竟然不忍直视的继承了。。。

{% highlight cpp %}
    static _Alloc _S_select_on_copy(const _Alloc& __a)
    { return _Base_type::select_on_container_copy_construction(__a); }
{% endhighlight %}

再回过头看基类的方法

{% highlight cpp %}
      static _Alloc
      select_on_container_copy_construction(const _Alloc& __rhs)
      { return _S_select(__rhs, 0); }
{% endhighlight %}
注释是 Obtain an allocator to use when copying a container. 好吧原来就是要做这事。

{% highlight cpp %}
      template<typename _Alloc2>
        struct __select_helper
        {
          template<typename _Alloc3, typename
            = decltype(std::declval<_Alloc3*>()
                ->select_on_container_copy_construction())>
            static true_type __test(int);
          template<typename>
            static false_type __test(...);
          using type = decltype(__test<_Alloc2>(0));
        };
      template<typename _Alloc2>
        using __has_soccc = typename __select_helper<_Alloc2>::type;
      template<typename _Alloc2,
               typename = _Require<__has_soccc<_Alloc2>>>
        static _Alloc2
        _S_select(_Alloc2& __a, int)
        { return __a.select_on_container_copy_construction(); }
      template<typename _Alloc2,
               typename = _Require<__not_<__has_soccc<_Alloc2>>>>
        static _Alloc2
        _S_select(_Alloc2& __a, ...)
        { return __a; }
{% endhighlight %}
又是用模板来做函数选择，目的就是在 allocator 里面有 select\_on\_container\_copy\_construction() 调用它来获得 allocator，没有的话就直接返回那个 allocator。为什么变得这么复杂？我们有一个 scoped\_allocator\_adaptor 没有去看过，答案就在那里。现在先略过，反正正常情况下，我们得到了 allocator 本身。

再看 \_\_uninitialized\_copy\_a

{% highlight cpp %}
  template<typename _ForwardIterator, typename _Size, typename _Tp,
           typename _Allocator>
    void
    __uninitialized_fill_n_a(_ForwardIterator __first, _Size __n,
                             const _Tp& __x, _Allocator& __alloc)
    {
      _ForwardIterator __cur = __first;
      __try
        {
          typedef __gnu_cxx::__alloc_traits<_Allocator> __traits;
          for (; __n > 0; --__n, ++__cur)
            __traits::construct(__alloc, std::__addressof(*__cur), __x);
        }
      __catch(...)
        {
          std::_Destroy(__first, __cur, __alloc);
          __throw_exception_again;
        }
    }

  template<typename _ForwardIterator, typename _Size, typename _Tp,
           typename _Tp2>
    inline void
    __uninitialized_fill_n_a(_ForwardIterator __first, _Size __n,
                             const _Tp& __x, allocator<_Tp2>&)
    { std::uninitialized_fill_n(__first, __n, __x); }
{% endhighlight %}

其实跟之前 那个 default\_uninitialized\_fill 差不多。都是判断如果是 trivial construct 的话，就忽略掉 construct 的过程。一般情况下我们都是 std::allocator，会匹配到第二个函数模板，之后的事情基本都是相同的，在此就略掉了。

后面相似的还有 \_\_uninitialized\_copy\_a， \_\_uninitialized\_move\_a 等等。

继续往下看 vector。

{% highlight cpp %}
      vector(initializer_list<value_type> __l,
             const allocator_type& __a = allocator_type())
      : _Base(__a)
      {
        _M_range_initialize(__l.begin(), __l.end(),
                            random_access_iterator_tag());
      }
{% endhighlight %}

\_M\_range\_initialize 有两个重载 

{% highlight cpp %}
      // Called by the second initialize_dispatch above
      template<typename _InputIterator>
        void
        _M_range_initialize(_InputIterator __first,
                            _InputIterator __last, std::input_iterator_tag)
        {
          for (; __first != __last; ++__first)
#if __cplusplus >= 201103L
            emplace_back(*__first);
#else
            push_back(*__first);
#endif
        }
      // Called by the second initialize_dispatch above
      template<typename _ForwardIterator>
        void
        _M_range_initialize(_ForwardIterator __first,
                            _ForwardIterator __last, std::forward_iterator_tag)
        {
          const size_type __n = std::distance(__first, __last);
          this->_M_impl._M_start = this->_M_allocate(__n);
          this->_M_impl._M_end_of_storage = this->_M_impl._M_start + __n;
          this->_M_impl._M_finish =
            std::__uninitialized_copy_a(__first, __last,
                                        this->_M_impl._M_start,
                                        _M_get_Tp_allocator());
        }
{% endhighlight %}

input\_iterator\_tag 情况下是一个一个进行 emplace\_back，forward\_iterator\_tag 情况下是做整体 copy。那 random\_access\_iterator\_tag 是那种呢？

{% highlight cpp %}
  /// Marking input iterators.
  struct input_iterator_tag { };
  /// Marking output iterators.
  struct output_iterator_tag { };
  /// Forward iterators support a superset of input iterator operations.
  struct forward_iterator_tag : public input_iterator_tag { };
  /// Bidirectional iterators support a superset of forward iterator
  /// operations.
  struct bidirectional_iterator_tag : public forward_iterator_tag { };
  /// Random-access iterators support a superset of bidirectional
  /// iterator operations.
  struct random_access_iterator_tag : public bidirectional_iterator_tag { };
{% endhighlight %}

两种都是诶。。。 当然，forward 更进，better。 push\_back 和 emplace\_back 等下到后面说，继续看构造。

{% highlight cpp %}
#if __cplusplus >= 201103L
      template<typename _InputIterator,
               typename = std::_RequireInputIter<_InputIterator>>
        vector(_InputIterator __first, _InputIterator __last,
               const allocator_type& __a = allocator_type())
        : _Base(__a)
        { _M_initialize_dispatch(__first, __last, __false_type()); }
#else
      template<typename _InputIterator>
        vector(_InputIterator __first, _InputIterator __last,
               const allocator_type& __a = allocator_type())
        : _Base(__a)
        {
          // Check whether it's an integral type. If so, it's not an iterator.
          typedef typename std::__is_integer<_InputIterator>::__type _Integral;
          _M_initialize_dispatch(__first, __last, _Integral());
        }
#endif
{% endhighlight %}
看来是 C++11 的变化，当前两个参数是 integral 时，会有变化，看一下是怎么 dispatch 的。

{% highlight cpp %}
      // _GLIBCXX_RESOLVE_LIB_DEFECTS
      // 438. Ambiguity in the "do the right thing" clause
      template<typename _Integer>
        void
        _M_initialize_dispatch(_Integer __n, _Integer __value, __true_type)
        {
          this->_M_impl._M_start = _M_allocate(static_cast<size_type>(__n));
          this->_M_impl._M_end_of_storage =
            this->_M_impl._M_start + static_cast<size_type>(__n);
          _M_fill_initialize(static_cast<size_type>(__n), __value);
        }
      // Called by the range constructor to implement [23.1.1]/9
      template<typename _InputIterator>
        void
        _M_initialize_dispatch(_InputIterator __first, _InputIterator __last,
                               __false_type)
        {
          typedef typename std::iterator_traits<_InputIterator>::
            iterator_category _IterCategory;
          _M_range_initialize(__first, __last, _IterCategory());
        }
{% endhighlight %}

原来是怕接受到了不是 iterator 的类型，结果和之前的构造重载发生歧义。

构造结束了，是析构。
{% highlight cpp %}
      ~vector() _GLIBCXX_NOEXCEPT
      { std::_Destroy(this->_M_impl._M_start, this->_M_impl._M_finish,
                      _M_get_Tp_allocator()); }
{% endhighlight %}

析构是要自己做的，内存释放 base 会搞定。

{% highlight cpp %}
      vector&
      operator=(const vector& __x);
{% endhighlight %}

operator=(&) 被放到了 vector.tcc 里面。operator=(&) 非常长, 跟 copy ctor 比起来复杂了许多。
先看前半部分。

{% highlight cpp %}
  template<typename _Tp, typename _Alloc>
    vector<_Tp, _Alloc>&
    vector<_Tp, _Alloc>::
    operator=(const vector<_Tp, _Alloc>& __x)
    {
      if (&__x != this)
        {
#if __cplusplus >= 201103L
          if (_Alloc_traits::_S_propagate_on_copy_assign())
            {
              if (!_Alloc_traits::_S_always_equal()
                  && _M_get_Tp_allocator() != __x._M_get_Tp_allocator())
                {
                  // replacement allocator cannot free existing storage
                  this->clear();
                  _M_deallocate(this->_M_impl._M_start,
                                this->_M_impl._M_end_of_storage
                                - this->_M_impl._M_start);
                  this->_M_impl._M_start = nullptr;
                  this->_M_impl._M_finish = nullptr;
                  this->_M_impl._M_end_of_storage = nullptr;
                }
              std::__alloc_on_copy(_M_get_Tp_allocator(),
                                   __x._M_get_Tp_allocator());
            }
#endif
{% endhighlight %}

首先是 \_S\_propagate\_on\_copy\_assign
{% highlight cpp %}
    static constexpr bool _S_propagate_on_copy_assign()
    { return _Base_type::propagate_on_container_copy_assignment::value; }
{% endhighlight %}

{% highlight cpp %}
      /**
       * @brief The allocator's size type
       *
       * @c Alloc::size_type if that type exists, otherwise
       * <tt> make_unsigned<difference_type>::type </tt>
      */
      typedef __size_type size_type;
_GLIBCXX_ALLOC_TR_NESTED_TYPE(propagate_on_container_copy_assignment,
                              false_type)
{% endhighlight %}

{% highlight cpp %}
#define _GLIBCXX_ALLOC_TR_NESTED_TYPE(_NTYPE, _ALT) \
  private: \
  template<typename _Tp> \
    static typename _Tp::_NTYPE _S_##_NTYPE##_helper(_Tp*); \
  static _ALT _S_##_NTYPE##_helper(...); \
    typedef decltype(_S_##_NTYPE##_helper((_Alloc*)0)) __##_NTYPE; \
  public:
{% endhighlight %}

propagate\_on\_container\_move\_assignment 就是说 copy 的时候 allocator 是否要传给 copy 方，某人情况下式 false 的。而若是 true 时，且两个 allocator 不想等，则必须 clear 掉自己并释放内存，然后做 alloc\_on\_copy。

{% highlight cpp %}
  template<typename _Alloc>
    inline void
    __do_alloc_on_copy(_Alloc& __one, const _Alloc& __two, true_type)
    { __one = __two; }
  template<typename _Alloc>
    inline void
    __do_alloc_on_copy(_Alloc&, const _Alloc&, false_type)
    { }
  template<typename _Alloc>
    inline void __alloc_on_copy(_Alloc& __one, const _Alloc& __two)
    {
      typedef allocator_traits<_Alloc> __traits;
      typedef typename __traits::propagate_on_container_copy_assignment __pocca;
      __do_alloc_on_copy(__one, __two, __pocca());
    }
{% endhighlight %}

好吧，其实就是把 allocator 赋值过来而已~~~。继续看 operator= 接下来的逻辑。
{% highlight cpp %}
          const size_type __xlen = __x.size();
          if (__xlen > capacity())
            {
              pointer __tmp = _M_allocate_and_copy(__xlen, __x.begin(),
                                                   __x.end());
              std::_Destroy(this->_M_impl._M_start, this->_M_impl._M_finish,
                            _M_get_Tp_allocator());
              _M_deallocate(this->_M_impl._M_start,
                            this->_M_impl._M_end_of_storage
                            - this->_M_impl._M_start);
              this->_M_impl._M_start = __tmp;
              this->_M_impl._M_end_of_storage = this->_M_impl._M_start + __xlen;
            }
          else if (size() >= __xlen)
            {
              std::_Destroy(std::copy(__x.begin(), __x.end(), begin()),
                            end(), _M_get_Tp_allocator());
            }
          else
            {
              std::copy(__x._M_impl._M_start, __x._M_impl._M_start + size(),
                        this->_M_impl._M_start);
              std::__uninitialized_copy_a(__x._M_impl._M_start + size(),
                                          __x._M_impl._M_finish,
                                          this->_M_impl._M_finish,
                                          _M_get_Tp_allocator());
            }
          this->_M_impl._M_finish = this->_M_impl._M_start + __xlen;
        }
      return *this;
    } 
{% endhighlight %}

如果地方不够用的话，首先分配内存进行 copy。
{% highlight cpp %}
      template<typename _ForwardIterator>
        pointer
        _M_allocate_and_copy(size_type __n,
                             _ForwardIterator __first, _ForwardIterator __last)
        {
          pointer __result = this->_M_allocate(__n);
          __try
            {
              std::__uninitialized_copy_a(__first, __last, __result,
                                          _M_get_Tp_allocator());
              return __result;
            }
          __catch(...)
            {
              _M_deallocate(__result, __n);
              __throw_exception_again;
            }
        }
{% endhighlight %}

然后再对自己的对象做析构，销毁内存，然后把 this-&gt;\_M\_impl 的三个指针调整过来。

如果本身的 size 太大呢？ 则会调用 std::copy 拷过来，然后把后面的都 \_Destroy 掉。
如果以上两种情况都不是，那么 size() &lt;\_\_xlen &lt;= capacity() ，这时还是 copy，只要最后调整 \_M\_finish 的位置就可以了。

继续看 vector 成员

{% highlight cpp %}
      vector&
      operator=(vector&& __x) noexcept(_Alloc_traits::_S_nothrow_move())
      {
        constexpr bool __move_storage =
          _Alloc_traits::_S_propagate_on_move_assign()
          || _Alloc_traits::_S_always_equal();
        _M_move_assign(std::move(__x),
                       integral_constant<bool, __move_storage>());
        return *this;
      }
{% endhighlight %}

{% highlight cpp %}
#if __cplusplus >= 201103L
    private:
      // Constant-time move assignment when source object's memory can be
      // moved, either because the source's allocator will move too
      // or because the allocators are equal.
      void
      _M_move_assign(vector&& __x, std::true_type) noexcept
      {
        vector __tmp(get_allocator());
        this->_M_impl._M_swap_data(__tmp._M_impl);
        this->_M_impl._M_swap_data(__x._M_impl);
        std::__alloc_on_move(_M_get_Tp_allocator(), __x._M_get_Tp_allocator());
      }

      // Do move assignment when it might not be possible to move source
      // object's memory, resulting in a linear-time operation.
      void
      _M_move_assign(vector&& __x, std::false_type)
      {
        if (__x._M_get_Tp_allocator() == this->_M_get_Tp_allocator())
          _M_move_assign(std::move(__x), std::true_type());
        else
          {
            // The rvalue's allocator cannot be moved and is not equal,
            // so we need to individually move each element.
            this->assign(std::__make_move_if_noexcept_iterator(__x.begin()),
                         std::__make_move_if_noexcept_iterator(__x.end()));
            __x.clear();
          }
      }
#endif
{% endhighlight %}

如果 allocator 是 propagate\_on\_move\_assign 或者总是相同的话（无状态），那么可以直接拿三个指针过来好了。但是如果不行的话，而且 allocator 不相等，则必须调用 assign，并且 clear 掉对方 vector。

{% highlight cpp %}
      vector&
      operator=(initializer_list<value_type> __l)
      {
        this->assign(__l.begin(), __l.end());
        return *this;
      }
{% endhighlight %}

发现 init list 里面也要 assgin，那来看 assign 的实现好了。

{% highlight cpp %}
      void
      assign(size_type __n, const value_type& __val)
      { _M_fill_assign(__n, __val); }
{% endhighlight %}

{% highlight cpp %}
  template<typename _Tp, typename _Alloc>
    void
    vector<_Tp, _Alloc>::
    _M_fill_assign(size_t __n, const value_type& __val)
    {
      if (__n > capacity())
        {
          vector __tmp(__n, __val, _M_get_Tp_allocator());
          __tmp.swap(*this);
        }
      else if (__n > size())
        {
          std::fill(begin(), end(), __val);
          std::__uninitialized_fill_n_a(this->_M_impl._M_finish,
                                        __n - size(), __val,
                                        _M_get_Tp_allocator());
          this->_M_impl._M_finish += __n - size();
        }
      else
        _M_erase_at_end(std::fill_n(this->_M_impl._M_start, __n, __val));
    }
{% endhighlight %}

跟刚才 operator= 的逻辑基本一样。。。不过看错 assgin 了，要看的是 assign(iterator, iterator)

{% highlight cpp %}
#if __cplusplus >= 201103L
      template<typename _InputIterator,
               typename = std::_RequireInputIter<_InputIterator>>
        void
        assign(_InputIterator __first, _InputIterator __last)
        { _M_assign_dispatch(__first, __last, __false_type()); }
#else
      template<typename _InputIterator>
        void
        assign(_InputIterator __first, _InputIterator __last)
        {
          // Check whether it's an integral type. If so, it's not an iterator.
          typedef typename std::__is_integer<_InputIterator>::__type _Integral;
          _M_assign_dispatch(__first, __last, _Integral());
        }
#endif
{% endhighlight %}
这个原因跟之前 ctor 差不多，继续看里面的 dispatch

{% highlight cpp %}
      // _GLIBCXX_RESOLVE_LIB_DEFECTS
      // 438. Ambiguity in the "do the right thing" clause
      template<typename _Integer>
        void
        _M_assign_dispatch(_Integer __n, _Integer __val, __true_type)
        { _M_fill_assign(__n, __val); }
      // Called by the range assign to implement [23.1.1]/9
      template<typename _InputIterator>
        void
        _M_assign_dispatch(_InputIterator __first, _InputIterator __last,
                           __false_type)
        {
          typedef typename std::iterator_traits<_InputIterator>::
            iterator_category _IterCategory;
          _M_assign_aux(__first, __last, _IterCategory());
        }
{% endhighlight %}

如果是 input iterator 的话，我们就只能一个一个赋值。如果最后有多余则 erase 掉，若空间不够，则调 insert 做插入。
{% highlight cpp %}
  template<typename _Tp, typename _Alloc>
    template<typename _InputIterator>
      void
      vector<_Tp, _Alloc>::
      _M_assign_aux(_InputIterator __first, _InputIterator __last,
                    std::input_iterator_tag)
      {
        pointer __cur(this->_M_impl._M_start);
        for (; __first != __last && __cur != this->_M_impl._M_finish;
             ++__cur, ++__first)
          *__cur = *__first;
        if (__first == __last)
          _M_erase_at_end(__cur);
        else
          insert(end(), __first, __last);
      }
{% endhighlight %}

如果是 forward iterator 的话，那就好办了，直接按长度的各种情况做 copy 什么的

{% highlight cpp %}
  template<typename _Tp, typename _Alloc>
    template<typename _ForwardIterator>
      void
      vector<_Tp, _Alloc>::
      _M_assign_aux(_ForwardIterator __first, _ForwardIterator __last,
                    std::forward_iterator_tag)
      {
        const size_type __len = std::distance(__first, __last);
        if (__len > capacity())
          {
            pointer __tmp(_M_allocate_and_copy(__len, __first, __last));
            std::_Destroy(this->_M_impl._M_start, this->_M_impl._M_finish,
                          _M_get_Tp_allocator());
            _M_deallocate(this->_M_impl._M_start,
                          this->_M_impl._M_end_of_storage
                          - this->_M_impl._M_start);
            this->_M_impl._M_start = __tmp;
            this->_M_impl._M_finish = this->_M_impl._M_start + __len;
            this->_M_impl._M_end_of_storage = this->_M_impl._M_finish;
          }
        else if (size() >= __len)
          _M_erase_at_end(std::copy(__first, __last, this->_M_impl._M_start));
        else
          {
            _ForwardIterator __mid = __first;
            std::advance(__mid, size());
            std::copy(__first, __mid, this->_M_impl._M_start);
            this->_M_impl._M_finish =
              std::__uninitialized_copy_a(__mid, __last,
                                          this->_M_impl._M_finish,
                                          _M_get_Tp_allocator());
          }
      }
{% endhighlight %}

看起来代码是和 operator= 相同的。
那 insert 呢？

{% highlight cpp %}
#if __cplusplus >= 201103L
    insert(const_iterator __position, const value_type& __x)
#else
    insert(iterator __position, const value_type& __x)
#endif
    {
      const size_type __n = __position - begin();
      if (this->_M_impl._M_finish != this->_M_impl._M_end_of_storage
          && __position == end())
        {
          _Alloc_traits::construct(this->_M_impl, this->_M_impl._M_finish, __x);
          ++this->_M_impl._M_finish;
        }
      else
        {
#if __cplusplus >= 201103L
          if (this->_M_impl._M_finish != this->_M_impl._M_end_of_storage)
            {
              _Tp __x_copy = __x;
              _M_insert_aux(__position._M_const_cast(), std::move(__x_copy));
            }
          else
#endif
            _M_insert_aux(__position._M_const_cast(), __x);
        }
      return iterator(this->_M_impl._M_start + __n);
    }
{% endhighlight %}

如果 insert 是在最后的话，而且有空位，那么就直接在最后 construct。否则的话继续交给 \_M\_insert\_aux。看起来 \_M\_insert\_aux 比较喜欢接受右值。

为了观赏方便，我把 关于 \_\_cpluscplus 的宏都去掉了（很疼）。都以 201103L 为标准。
还是先看前半段。

{% highlight cpp %}
  template<typename _Tp, typename _Alloc>
    template<typename... _Args>
      void
      vector<_Tp, _Alloc>::
      _M_insert_aux(iterator __position, _Args&&... __args)
    {
      if (this->_M_impl._M_finish != this->_M_impl._M_end_of_storage)
        {
          _Alloc_traits::construct(this->_M_impl, this->_M_impl._M_finish,
                                   _GLIBCXX_MOVE(*(this->_M_impl._M_finish
                                                   - 1)));
          ++this->_M_impl._M_finish;
          _GLIBCXX_MOVE_BACKWARD3(__position.base(),
                                  this->_M_impl._M_finish - 2,
                                  this->_M_impl._M_finish - 1);
          *__position = _Tp(std::forward<_Args>(__args)...);
        }
{% endhighlight %}

还是，如果空间够用的话，把最后一个元素往后挪一位，然后再整体 move\_backward。（不能直接 move 原因是最开始 finish 后面是无效内存没法调 move），然后再 position 的位置上构造元素。

原来 STL 里面还有 move\_backward，move\_forward 这么奇妙的方法啊。
{% highlight cpp %}
#if __cplusplus >= 201103L
#define _GLIBCXX_MOVE_BACKWARD3(_Tp, _Up, _Vp) std::move_backward(_Tp, _Up, _Vp)
#else
#define _GLIBCXX_MOVE_BACKWARD3(_Tp, _Up, _Vp) std::copy_backward(_Tp, _Up, _Vp)
#endif
{% endhighlight %}

接着看下面空间不够的情况

{% highlight cpp %}
      else
        {
          const size_type __len =
            _M_check_len(size_type(1), "vector::_M_insert_aux");
          const size_type __elems_before = __position - begin();
          pointer __new_start(this->_M_allocate(__len));
          pointer __new_finish(__new_start);
          __try
            {
              // The order of the three operations is dictated by the C++0x
              // case, where the moves could alter a new element belonging
              // to the existing vector. This is an issue only for callers
              // taking the element by const lvalue ref (see 23.1/13).
              _Alloc_traits::construct(this->_M_impl,
                                       __new_start + __elems_before,
#if __cplusplus >= 201103L
                                       std::forward<_Args>(__args)...);
#else
                                       __x);
#endif
              __new_finish = pointer();
              __new_finish
                = std::__uninitialized_move_if_noexcept_a
                (this->_M_impl._M_start, __position.base(),
                 __new_start, _M_get_Tp_allocator());
              ++__new_finish;
              __new_finish
                = std::__uninitialized_move_if_noexcept_a
                (__position.base(), this->_M_impl._M_finish,
                 __new_finish, _M_get_Tp_allocator());
            }
          __catch(...)
            {
              if (!__new_finish)
                _Alloc_traits::destroy(this->_M_impl,
                                       __new_start + __elems_before);
              else
                std::_Destroy(__new_start, __new_finish, _M_get_Tp_allocator());
              _M_deallocate(__new_start, __len);
              __throw_exception_again;
            }
          std::_Destroy(this->_M_impl._M_start, this->_M_impl._M_finish,
                        _M_get_Tp_allocator());
          _M_deallocate(this->_M_impl._M_start,
                        this->_M_impl._M_end_of_storage
                        - this->_M_impl._M_start);
          this->_M_impl._M_start = __new_start;
          this->_M_impl._M_finish = __new_finish;
          this->_M_impl._M_end_of_storage = __new_start + __len;
        }
    }
{% endhighlight %}

一旦要重新分配内存，麻烦事就来了。分配好内存之后，现在原来的位置上构造好 insert 的对象，然后再 move 前后两部分。注意到注释的那段话，msvc 之前还出过 bug 。。 http://stackoverflow.com/questions/11653111/stdvector-inconsistent-crash-between-push-back-and-insertend-x

注意到 \_M\_check\_len，这是 len 改变的地方。

{% highlight cpp %}
      // Called by the latter.
      size_type
      _M_check_len(size_type __n, const char* __s) const
      {
        if (max_size() - size() < __n)
          __throw_length_error(__N(__s));
        const size_type __len = size() + std::max(size(), __n);
        return (__len < size() || __len > max_size()) ? max_size() : __len;
      }
{% endhighlight %}

这就是 vector 空间不够用每次翻倍的地方啊~~~。

如果是右值的版本，则会去转给 emplace
{% highlight cpp %}
      iterator
      insert(const_iterator __position, value_type&& __x)
      { return emplace(__position, std::move(__x)); }
{% endhighlight %}

{% highlight cpp %}
  template<typename _Tp, typename _Alloc>
    template<typename... _Args>
      typename vector<_Tp, _Alloc>::iterator
      vector<_Tp, _Alloc>::
      emplace(const_iterator __position, _Args&&... __args)
      {
        const size_type __n = __position - begin();
        if (this->_M_impl._M_finish != this->_M_impl._M_end_of_storage
            && __position == end())
          {
            _Alloc_traits::construct(this->_M_impl, this->_M_impl._M_finish,
                                     std::forward<_Args>(__args)...);
            ++this->_M_impl._M_finish;
          }
        else
          _M_insert_aux(__position._M_const_cast(),
                        std::forward<_Args>(__args)...);
        return iterator(this->_M_impl._M_start + __n);
      }
{% endhighlight %}

其实跟之前的 insert 并没有什么差别（当然还是有一点点点的）

insert 还有 fill 版本的，iterator 版本的。其实道理跟之前都一样，aux 做检查转发，然后到内部判断大小是否合适，决定内存分配，move，或者 copy，异常处理等等。真的会看腻。

已经不想看了，现在开始尽情 yy 吧。

erase 怎么做呢？ 如果是 erase 某个 position，那么就 destroy 掉，然后 move forward；如果是某个 range 呢，基本都差不多，记得最后要改 \_M\_finish。如果是 erase 的是 end 要做处理。

push\_back 和 emplace\_back 呢。大概都可以 yy 的到~~。

vector 还有一个经常被用到的 shrink\_to\_fit，以前是这样做的

{% highlight cpp %}
std::vector<double>(myvector).swap(myvector);
{% endhighlight %}

现在提供了函数
{% highlight cpp %}
#if __cplusplus >= 201103L
      /** A non-binding request to reduce capacity() to size(). */
      void
      shrink_to_fit()
      { _M_shrink_to_fit(); }
#endif
{% endhighlight %}

{% highlight cpp %}
  template<typename _Tp, typename _Alloc>
    bool
    vector<_Tp, _Alloc>::
    _M_shrink_to_fit()
    {
      if (capacity() == size())
        return false;
      return std::__shrink_to_fit_aux<vector>::_S_do_it(*this);
    }
{% endhighlight %}

让人发指的是，它竟然被放到了 allocator.h 里面

{% highlight cpp %}
#if __cplusplus >= 201103L
  template<typename _Tp, bool
    = __or_<is_copy_constructible<typename _Tp::value_type>,
            is_nothrow_move_constructible<typename _Tp::value_type>>::value>
    struct __shrink_to_fit_aux
    { static bool _S_do_it(_Tp&) noexcept { return false; } };
  template<typename _Tp>
    struct __shrink_to_fit_aux<_Tp, true>
    {
      static bool
      _S_do_it(_Tp& __c) noexcept
      {
        __try
          {
            _Tp(__make_move_if_noexcept_iterator(__c.begin()),
                __make_move_if_noexcept_iterator(__c.end()),
                __c.get_allocator()).swap(__c);
            return true;
          }
        __catch(...)
          { return false; }
      }
    };
#endif
{% endhighlight %}

在是可 copy construct 或者 move nothrow 时才有效，一般这两点都会满足。其实里面也就是在做 swap 啦。。

看久了就会无聊，来换个口味，看下 vector 给我们返回的 iterator 到底是怎样的东西。

{% highlight cpp %}
  template<typename _Category, typename _Tp, typename _Distance = ptrdiff_t,
           typename _Pointer = _Tp*, typename _Reference = _Tp&>
    struct iterator
    {
      /// One of the @link iterator_tags tag types@endlink.
      typedef _Category iterator_category;
      /// The type "pointed to" by the iterator.
      typedef _Tp value_type;
      /// Distance between iterators is represented as this type.
      typedef _Distance difference_type;
      /// This type represents a pointer-to-value_type.
      typedef _Pointer pointer;
      /// This type represents a reference-to-value_type.
      typedef _Reference reference;
    };
{% endhighlight %}

也就是一个 struct 啦，vector 用到了这几种 iterator
{% highlight cpp %}
      typedef __gnu_cxx::__normal_iterator<pointer, vector> iterator;
      typedef __gnu_cxx::__normal_iterator<const_pointer, vector>
      const_iterator;
      typedef std::reverse_iterator<const_iterator> const_reverse_iterator;
      typedef std::reverse_iterator<iterator> reverse_iterator;
{% endhighlight %}

首先， \_\_normal\_iterator
{% highlight cpp %}
  template<typename _Iterator, typename _Container>
    class __normal_iterator
    {
    protected:
      _Iterator _M_current;
      typedef iterator_traits<_Iterator> __traits_type;
    public:
      typedef _Iterator iterator_type;
      typedef typename __traits_type::iterator_category iterator_category;
      typedef typename __traits_type::value_type value_type;
      typedef typename __traits_type::difference_type difference_type;
      typedef typename __traits_type::reference reference;
      typedef typename __traits_type::pointer pointer;
      _GLIBCXX_CONSTEXPR __normal_iterator() _GLIBCXX_NOEXCEPT
      : _M_current(_Iterator()) { }
      explicit
      __normal_iterator(const _Iterator& __i) _GLIBCXX_NOEXCEPT
      : _M_current(__i) { }

      // Allow iterator to const_iterator conversion
      template<typename _Iter>
        __normal_iterator(const __normal_iterator<_Iter,
                          typename __enable_if<
               (std::__are_same<_Iter, typename _Container::pointer>::__value),
                      _Container>::__type>& __i) _GLIBCXX_NOEXCEPT
        : _M_current(__i.base()) { }
#if __cplusplus >= 201103L
      __normal_iterator<typename _Container::pointer, _Container>
      _M_const_cast() const noexcept
      {
        using _PTraits = std::pointer_traits<typename _Container::pointer>;
        return __normal_iterator<typename _Container::pointer, _Container>
          (_PTraits::pointer_to(const_cast<typename _PTraits::element_type&>
                                (*_M_current)));
      }
#else
      __normal_iterator
      _M_const_cast() const
      { return *this; }
#endif
{% endhighlight %}

从指针构造 iterator，允许从 const 构造，允许从 const 里面返回一个非 const iterator （\_M\_const\_cast），主要是方便使用。继续往下。

接下来就是优秀的 operator 重载学习模板了。。。。
{% highlight cpp %}
      // Forward iterator requirements
      reference
      operator*() const _GLIBCXX_NOEXCEPT
      { return *_M_current; }
      pointer
      operator->() const _GLIBCXX_NOEXCEPT
      { return _M_current; }
      __normal_iterator&
      operator++() _GLIBCXX_NOEXCEPT
      {
        ++_M_current;
        return *this;
      }
      __normal_iterator
      operator++(int) _GLIBCXX_NOEXCEPT
      { return __normal_iterator(_M_current++); }
      // Bidirectional iterator requirements
      __normal_iterator&
      operator--() _GLIBCXX_NOEXCEPT
      {
        --_M_current;
        return *this;
      }
      __normal_iterator
      operator--(int) _GLIBCXX_NOEXCEPT
      { return __normal_iterator(_M_current--); }
      // Random access iterator requirements
      reference
      operator[](difference_type __n) const _GLIBCXX_NOEXCEPT
      { return _M_current[__n]; }

      __normal_iterator&
      operator+=(difference_type __n) _GLIBCXX_NOEXCEPT
      { _M_current += __n; return *this; }
      __normal_iterator
      operator+(difference_type __n) const _GLIBCXX_NOEXCEPT
      { return __normal_iterator(_M_current + __n); }
      __normal_iterator&
      operator-=(difference_type __n) _GLIBCXX_NOEXCEPT
      { _M_current -= __n; return *this; }
      __normal_iterator
      operator-(difference_type __n) const _GLIBCXX_NOEXCEPT
      { return __normal_iterator(_M_current - __n); }
      const _Iterator&
      base() const _GLIBCXX_NOEXCEPT
      { return _M_current; }
{% endhighlight %}

可见 normal\_iterator 是一个最强大的 iterator。。。 当然后面还有各种比较 operator。

哦对了，说道这里，刚才 vector 的 compare 忘记了。

{% highlight cpp %}
  template<typename _Tp, typename _Alloc>
    inline bool
    operator==(const vector<_Tp, _Alloc>& __x, const vector<_Tp, _Alloc>& __y)
    { return (__x.size() == __y.size()
              && std::equal(__x.begin(), __x.end(), __y.begin())); }

  template<typename _Tp, typename _Alloc>
    inline bool
    operator<(const vector<_Tp, _Alloc>& __x, const vector<_Tp, _Alloc>& __y)
    { return std::lexicographical_compare(__x.begin(), __x.end(),
                                          __y.begin(), __y.end()); }
{% endhighlight %}

\= \= 和 &lt; 向来都是说明问题的两个。

还有幽默感十足的 reverse\_iterator。

{% highlight cpp %}
  template<typename _Iterator>
    class reverse_iterator
    : public iterator<typename iterator_traits<_Iterator>::iterator_category,
                      typename iterator_traits<_Iterator>::value_type,
                      typename iterator_traits<_Iterator>::difference_type,
                      typename iterator_traits<_Iterator>::pointer,
                      typename iterator_traits<_Iterator>::reference>
    {
    protected:
      _Iterator current;
{% endhighlight %}

关键在后面

{% highlight cpp %}
      /**
       * @return A reference to the value at @c --current
       *
       * This requires that @c --current is dereferenceable.
       *
       * @warning This implementation requires that for an iterator of the
       * underlying iterator type, @c x, a reference obtained by
       * @c *x remains valid after @c x has been modified or
       * destroyed. This is a bug: http://gcc.gnu.org/PR51823
      */
      reference
      operator*() const
      {
        _Iterator __tmp = current;
        return *--__tmp;
      }
      /**
       * @return A pointer to the value at @c --current
       *
       * This requires that @c --current is dereferenceable.
      */
      pointer
      operator->() const
      { return &(operator*()); }
{% endhighlight %}

\= \= 反正我觉得我不会用 reverse\_iterator ..... 或许库里某个地方谁会用到？
reverse 的含义就是 ++ 是 --， -- 是 ++

{% highlight cpp %}
      reverse_iterator&
      operator++()
      {
        --current;
        return *this;
      }
{% endhighlight %}

好了，就不深究。
### 总结一下
1. vector 的坑还不算深，不过总体看的感觉代码冗余非常严重，可能也是无奈
2. uninitialized copy, move 以及 trivial construct, destruct 这种优化不错恩~
3. \_Vector\_base 这种内存管理的方式值得借鉴
