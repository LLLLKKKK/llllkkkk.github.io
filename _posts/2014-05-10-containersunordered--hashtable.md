---
layout: post
title: "containers，unordered 系列与 hashtable"
description: ""
category: C++
tags: [C++, STL, code reading]
---
{% include JB/setup %}
总算把中期报告搞定了，可以继续搞起。
​
C++11 中， 多了 4 个 unordered 容器，分别是 unordered\_set, unordered\_multiset, unordered\_map, unordered\_multimap。当然，也略有耳闻里面是用 hash table 来做的，今天一探究竟。

先来看看 unordered\_map, `include/bits/unordered_map.h`
{% highlight cpp %}
  template<class _Key, class _Tp,
           class _Hash = hash<_Key>,
           class _Pred = std::equal_to<_Key>,
           class _Alloc = std::allocator<std::pair<const _Key, _Tp> > >
    class unordered_map
    {
      typedef __umap_hashtable<_Key, _Tp, _Hash, _Pred, _Alloc> _Hashtable;
      _Hashtable _M_h;
{% endhighlight %}

发现里面有一个 \_Hashtable，相似的在 multimap 中。
{% highlight cpp %}
  template<class _Key, class _Tp,
           class _Hash = hash<_Key>,
           class _Pred = std::equal_to<_Key>,
           class _Alloc = std::allocator<std::pair<const _Key, _Tp> > >
    class unordered_multimap
    {
      typedef __ummap_hashtable<_Key, _Tp, _Hash, _Pred, _Alloc> _Hashtable;
      _Hashtable _M_h;
{% endhighlight %}

<!--more-->
注意到不同之处是 `__umap_hashtable` 和 `__ummap_hashtable`，猜测应该是后面 hashtable 的实现是一直的，不过外面用 trait 进行了不同的特化。unordered\_set 也是用类似方法实现。

继续深入一步。先从 map 入手，来看  `__umap_hashtable` 和 `__ummap_hashtable`。
{% highlight cpp %}
  /// Base types for unordered_map.
  template<bool _Cache>
    using __umap_traits = __detail::_Hashtable_traits<_Cache, false, true>;
  template<typename _Key,
           typename _Tp,
           typename _Hash = hash<_Key>,
           typename _Pred = std::equal_to<_Key>,
           typename _Alloc = std::allocator<std::pair<const _Key, _Tp> >,
           typename _Tr = __umap_traits<__cache_default<_Key, _Hash>::value>>
    using __umap_hashtable = _Hashtable<_Key, std::pair<const _Key, _Tp>,
                                        _Alloc, __detail::_Select1st,
                                        _Pred, _Hash,
                                        __detail::_Mod_range_hashing,
                                        __detail::_Default_ranged_hash,
                                        __detail::_Prime_rehash_policy, _Tr>;
{% endhighlight %}
`_Hashtable` 竟然需要这么多模板参数。先来看 `__umap_hashtable` 上的模板参数 `_Tr`。（ps. 常见手法，把内部的实现扔到 detail namespace 里面）。

`include/bits/hashtable.h`
{% highlight cpp %}
  template<typename _Tp, typename _Hash>
    using __cache_default
      = __not_<__and_<// Do not cache for fast hasher.
                       __is_fast_hash<_Hash>,
                       // Mandatory to have erase not throwing.
                       __detail::__is_noexcept_hash<_Tp, _Hash>>>;
{% endhighlight %}

原来是判断要不要 cache 住 hash key 的结果。顺便来看一下 noexcept 是怎么检测的。

{% highlight cpp %}
  // Helper type used to detect whether the hash functor is noexcept.
  template <typename _Key, typename _Hash>
    struct __is_noexcept_hash : std::integral_constant<bool,
        noexcept(declval<const _Hash&>()(declval<const _Key&>()))>
    { };
{% endhighlight %}
= = 原来又是 std::declval 来做”函数调用“啊。还有，什么样的 hash 是 fast hash 呢？

{% highlight cpp %}
./functional_hash.h:202: struct __is_fast_hash : public std::true_type
./functional_hash.h:206: struct __is_fast_hash<hash<long double>> : public std::false_type
./hashtable.h:44: __is_fast_hash<_Hash>,
./basic_string.h:3072: struct __is_fast_hash<hash<string>> : std::false_type
./basic_string.h:3088: struct __is_fast_hash<hash<wstring>> : std::false_type
./basic_string.h:3106: struct __is_fast_hash<hash<u16string>> : std::false_type
./basic_string.h:3121: struct __is_fast_hash<hash<u32string>> : std::false_type
{% endhighlight %}
除了 string 和 long double 之外的都是 fast hash。等最后记得看一下 hash func 是怎么做的。\_\_cache\_default 搞定了，来看 \_\_umap\_traits 的具体实现 \_Hashtable\_traits（ps. unordered\_set 也是用了 \_\_detail::\_Hashtable\_trait 来做）。

{% highlight cpp %}
  template<bool _Cache_hash_code, bool _Constant_iterators, bool _Unique_keys>
    struct _Hashtable_traits
    {
      template<bool _Cond>
        using __bool_constant = integral_constant<bool, _Cond>;
      using __hash_cached = __bool_constant<_Cache_hash_code>;
      using __constant_iterators = __bool_constant<_Constant_iterators>;
      using __unique_keys = __bool_constant<_Unique_keys>;
    };
{% endhighlight %}
1. \_\_hash\_cached 刚才已经看过，是由 hash func 决定的。
2. \_\_constant\_iterator 对于 map 是 false，对于 set 是 true。拿到 iterator 之后可以对 map 的内容做更改，然而对于 set 的 iterator 却无能为力。
3. \_\_unique\_keys  对于 multi 是 false，否则 true（这就不用解释了吧~）。

\_Hashtable\_traits 搞定了，他为 map/set，multi/unqiue 提供了封装。接下来就要看 \_Hashtable 的真面目了。\_Hashtable 上一坨模板参数，用意何在？

{% highlight cpp %}
  template<typename _Key, typename _Value, typename _Alloc,
           typename _ExtractKey, typename _Equal,
           typename _H1, typename _H2, typename _Hash,
           typename _RehashPolicy, typename _Traits>
    class _Hashtable
{% endhighlight %}

1. \_Key，\_Value，\_Alloc 这些很明显了。不同之处是， set 的 \_Value 就是 \_Key，而 map 的 \_Value 是 pair<const _Key, _Value>。
2. 因为 _Value 的不同，所以 _ExtractKey 的过程也不同咯（毕竟要把原来的 _Value 存下来么，要不然怎么 rehash）。
{% highlight cpp %}
  struct _Identity
  {
    template<typename _Tp>
      _Tp&&
      operator()(_Tp&& __x) const
      { return std::forward<_Tp>(__x); }
  };
  struct _Select1st
  {
    template<typename _Tp>
      auto
      operator()(_Tp&& __x) const
      -> decltype(std::get<0>(std::forward<_Tp>(__x)))
      { return std::get<0>(std::forward<_Tp>(__x)); }
  };
{% endhighlight %}
3. \_Pred = std::equal\_to&lt;\_Key&gt;，这个没什么好说的。
4. \_H1 一直都是 hash&lt;\_Key&gt;，也就是 std::hash，用来 hash \_Key 的； \_H2 为 \_Mod\_range\_hashing，也就是把 \_Key hash 的结果再 hash 进 bucket（bucket 数量小于 hash 的域）；\_Hash 为 \_Default\_ranged\_hash，其实只一个空类。\_H1  和 \_H2 是配套使用的两个参数，而 \_Hash 则是直接从 \_Key hash 到 bucket 的方法。`_H1, _H2` 和 `_Hash` 其实是两个正交的方式，只能使用其一。
5. rehash 也就是冲撞之后寻找下个 bucket 的策略。
6. trait 之前分析过，里面带了三个有关 multi/unique，set/map 的 bool。

感到了这个世界满满的 policy based design 啊。继续来深入 \_Hash\_table。
{% highlight cpp %}
  template<typename _Key, typename _Value, typename _Alloc,
           typename _ExtractKey, typename _Equal,
           typename _H1, typename _H2, typename _Hash,
           typename _RehashPolicy, typename _Traits>
    class _Hashtable
    : public __detail::_Hashtable_base<_Key, _Value, _ExtractKey, _Equal,
                                       _H1, _H2, _Hash, _Traits>,
      public __detail::_Map_base<_Key, _Value, _Alloc, _ExtractKey, _Equal,
                                 _H1, _H2, _Hash, _RehashPolicy, _Traits>,
      public __detail::_Insert<_Key, _Value, _Alloc, _ExtractKey, _Equal,
                               _H1, _H2, _Hash, _RehashPolicy, _Traits>,
      public __detail::_Rehash_base<_Key, _Value, _Alloc, _ExtractKey, _Equal,
                                    _H1, _H2, _Hash, _RehashPolicy, _Traits>,
      public __detail::_Equality<_Key, _Value, _Alloc, _ExtractKey, _Equal,
                                 _H1, _H2, _Hash, _RehashPolicy, _Traits>,
      private __detail::_Hashtable_alloc<
        typename __alloctr_rebind<_Alloc,
          __detail::_Hash_node<_Value,
                               _Traits::__hash_cached::value> >::__type>
{% endhighlight %}

看起来很恐怖吧。。。这么做的原因呢？ [Curiously Recurring Template Pattern (CRTP)](http://en.wikipedia.org/wiki/Curiously_recurring_template_pattern)。就是为了避免使用虚表多一层虚函数查找。

而这些基类将 hashtable 的过程进行分解，尽量做到类之间的功能正交。不得不说这是一个非常好的设计。

看名字大概可以猜出基类里面都在做什么，分别有 `_Hashtable_base`, `_Map_base`, `_Insert`, `_Rehash_base`, `_Equality` ,`_Hashtable_alloc`。一个一个来。

{% highlight cpp %}
  template<typename _Key, typename _Value,
           typename _ExtractKey, typename _Equal,
           typename _H1, typename _H2, typename _Hash, typename _Traits>
  struct _Hashtable_base
  : public _Hash_code_base<_Key, _Value, _ExtractKey, _H1, _H2, _Hash,
                           _Traits::__hash_cached::value>,
    private _Hashtable_ebo_helper<0, _Equal>
{% endhighlight %}

原来还有一层 \_Hash\_code\_base。 ebo 就不解释了~。

\_Hash\_code\_base 一共有四种特化：
{% highlight cpp %}
// 启用 _Hash（自定义，不是 _Default_ranged_hash）, _H1, _H2 废弃, 不启用 cache
  template<typename _Key, typename _Value, typename _ExtractKey,
           typename _H1, typename _H2, typename _Hash>
    struct _Hash_code_base<_Key, _Value, _ExtractKey, _H1, _H2, _Hash, false>
    : private _Hashtable_ebo_helper<0, _ExtractKey>,
      private _Hashtable_ebo_helper<1, _Hash>
// 启用 _Hash （自定义，不是 _Default_ranged_hash），此时 cache 没有意义，所以只给出定义没有实现（肯定挂）。
  template<typename _Key, typename _Value, typename _ExtractKey,
           typename _H1, typename _H2, typename _Hash>
    struct _Hash_code_base<_Key, _Value, _ExtractKey, _H1, _H2, _Hash, true>;

// _Hash 是 _Default_ranged_hash，启用 _H1, _H2, 不启用 cache
  template<typename _Key, typename _Value, typename _ExtractKey,
           typename _H1, typename _H2>
    struct _Hash_code_base<_Key, _Value, _ExtractKey, _H1, _H2,
                           _Default_ranged_hash, false>
    : private _Hashtable_ebo_helper<0, _ExtractKey>,
      private _Hashtable_ebo_helper<1, _H1>,
      private _Hashtable_ebo_helper<2, _H2>

// _Hash 是 _Default_ranged_hash，启用 _H1, _H2, 启用 cache
  template<typename _Key, typename _Value, typename _ExtractKey,
           typename _H1, typename _H2>
    struct _Hash_code_base<_Key, _Value, _ExtractKey, _H1, _H2,
                           _Default_ranged_hash, true>
    : private _Hashtable_ebo_helper<0, _ExtractKey>,
      private _Hashtable_ebo_helper<1, _H1>,
      private _Hashtable_ebo_helper<2, _H2>
{% endhighlight %}

先看第一种，\_Hash & no cache。不过标准容器都不是这种情况。

{% highlight cpp %}
    private:
      using __ebo_extract_key = _Hashtable_ebo_helper<0, _ExtractKey>;
      using __ebo_hash = _Hashtable_ebo_helper<1, _Hash>;
    protected:
      typedef void* __hash_code;
      typedef _Hash_node<_Value, false> __node_type;
      // We need the default constructor for the local iterators.
      _Hash_code_base() = default;
      _Hash_code_base(const _ExtractKey& __ex, const _H1&, const _H2&,
                      const _Hash& __h)
      : __ebo_extract_key(__ex), __ebo_hash(__h) { }
      __hash_code
      _M_hash_code(const _Key& __key) const
      { return 0; }
{% endhighlight %}

因为这里没有 \_H1，hash\_code 只是一个 dummy 实现。实现都平淡无奇。
关键是这里：

{% highlight cpp %}
      std::size_t
      _M_bucket_index(const _Key& __k, __hash_code, std::size_t __n) const
      { return _M_ranged_hash()(__k, __n); }
      std::size_t
      _M_bucket_index(const __node_type* __p, std::size_t __n) const
        noexcept( noexcept(declval<const _Hash&>()(declval<const _Key&>(),
                                                   (std::size_t)0)) )
      { return _M_ranged_hash()(_M_extract()(__p->_M_v()), __n); }

      const _Hash&
      _M_ranged_hash() const { return __ebo_hash::_S_cget(*this); }
      _Hash&
      _M_ranged_hash() { return __ebo_hash::_S_get(*this); }
{% endhighlight %}

顺便看一下 \_S\_get，就是想拿基类。

{% highlight cpp %}
      static _Tp&
      _S_get(_Hashtable_ebo_helper& __eboh)
      { return static_cast<_Tp&>(__eboh); }
{% endhighlight %}

ranged\_hash 就是给定 Key 和域 N，hash 到 N 中。当然 default 情况下，ranged\_hash 就是 \_H2(\_H1(\_Key), N)。

当然，\_Hash\_code\_base 还有需要一些其他方法，提供为外部做接口，这里大多是空。之后的重点就是看这些接口的实现是怎样的，跟这种特化有什么区别。

{% highlight cpp %}
      void
      _M_store_code(__node_type*, __hash_code) const
      { }
      void
      _M_copy_code(__node_type*, const __node_type*) const
      { }
      void
      _M_swap(_Hash_code_base& __x)
      {
        std::swap(_M_extract(), __x._M_extract());
        std::swap(_M_ranged_hash(), __x._M_ranged_hash());
      }
      const _ExtractKey&
      _M_extract() const { return __ebo_extract_key::_S_cget(*this); }
      _ExtractKey&
      _M_extract() { return __ebo_extract_key::_S_get(*this); }
{% endhighlight %}

下一种，\_Hash ==  \_Default\_ranged\_hash && no cache。

{% highlight cpp %}
      using __ebo_h1 = _Hashtable_ebo_helper<1, _H1>;
      using __ebo_h2 = _Hashtable_ebo_helper<2, _H2>;

      std::size_t
      _M_bucket_index(const _Key&, __hash_code __c, std::size_t __n) const
      { return _M_h2()(__c, __n); }
      std::size_t
      _M_bucket_index(const __node_type* __p, std::size_t __n) const
        noexcept( noexcept(declval<const _H1&>()(declval<const _Key&>()))
                  && noexcept(declval<const _H2&>()((__hash_code)0,
                                                    (std::size_t)0)) )
      { return _M_h2()(_M_h1()(_M_extract()(__p->_M_v())), __n); }

      const _H1&
      _M_h1() const { return __ebo_h1::_S_cget(*this); }

      _H2&
      _M_h2() { return __ebo_h2::_S_get(*this); }
{% endhighlight %}

就这点变化，也就是用 \_H1，\_H2 做 hash。那接下来继续看，cache 启用了之后是什么效果呢？应该是 copy node 时候有变化吧~

{% highlight cpp %}
      void
      _M_store_code(__node_type* __n, __hash_code __c) const
      { __n->_M_hash_code = __c; }
      void
      _M_copy_code(__node_type* __to, const __node_type* __from) const
      { __to->_M_hash_code = __from->_M_hash_code; }
{% endhighlight %}

对，就是这样的。外部新增 node 时就会调 store，赋值就会调 copy，而编译器模板匹配完成之后，就会调用到各自特化的函数中去~~ 这样的类模板设计接口，然后编译器达到多态真是赞啊~~~

\_Hash\_code\_base结束，回到子类 \_Hashtable\_base。

{% highlight cpp %}
    using iterator = __detail::_Node_iterator<value_type,
                                              __constant_iterators::value,
                                              __hash_cached::value>;
    using const_iterator = __detail::_Node_const_iterator<value_type,
                                                   __constant_iterators::value,
                                                   __hash_cached::value>;
    using local_iterator = __detail::_Local_iterator<key_type, value_type,
                                                  _ExtractKey, _H1, _H2, _Hash,
                                                  __constant_iterators::value,
                                                     __hash_cached::value>;
    using const_local_iterator = __detail::_Local_const_iterator<key_type,
                                                                 value_type,
                                        _ExtractKey, _H1, _H2, _Hash,
                                        __constant_iterators::value,
                                        __hash_cached::value>;
{% endhighlight %}

在这里定义了各种 iterator，不过暂时没什么关系，先不用看。
比较有用的是这个 Equal

{% highlight cpp %}
  private:
    using _EqualEBO = _Hashtable_ebo_helper<0, _Equal>;
    using _EqualHelper = _Equal_helper<_Key, _Value, _ExtractKey, _Equal,
                                        __hash_code, __hash_cached::value>;
  protected:
    bool
    _M_equals(const _Key& __k, __hash_code __c, __node_type* __n) const
    {
      return _EqualHelper::_S_equals(_M_eq(), this->_M_extract(),
                                     __k, __c, __n);
    }

    _Equal&
    _M_eq() { return _EqualEBO::_S_get(*this); }
{% endhighlight %}

看一下 \_EqualHelper。

{% highlight cpp %}
  template<typename _Key, typename _Value, typename _ExtractKey,
           typename _Equal, typename _HashCodeType>
  struct _Equal_helper<_Key, _Value, _ExtractKey, _Equal, _HashCodeType, true>
  {
    static bool
    _S_equals(const _Equal& __eq, const _ExtractKey& __extract,
              const _Key& __k, _HashCodeType __c, _Hash_node<_Value, true>* __n)
    { return __c == __n->_M_hash_code && __eq(__k, __extract(__n->_M_v())); }
  };
  template<typename _Key, typename _Value, typename _ExtractKey,
           typename _Equal, typename _HashCodeType>
  struct _Equal_helper<_Key, _Value, _ExtractKey, _Equal, _HashCodeType, false>
  {
    static bool
    _S_equals(const _Equal& __eq, const _ExtractKey& __extract,
              const _Key& __k, _HashCodeType, _Hash_node<_Value, false>* __n)
    { return __eq(__k, __extract(__n->_M_v())); }
  };
{% endhighlight %}
原来是对是否 cache 做处理，hash code 有 cache 时判断 key 相等会先用 hash code 做比较（短路）。
那么也就是说，\_Hashtable\_base 封装了 hash 的计算和 cache 相关实现。

接下来，是 \_Hashtable 另一个父类，\_Map\_base。直接看里面的关键内容。

{% highlight cpp %}
      using key_type = typename __hashtable_base::key_type;
      using iterator = typename __hashtable_base::iterator;
      using mapped_type = typename std::tuple_element<1, _Pair>::type;

      mapped_type&
      operator[](const key_type& __k);
      mapped_type&
      operator[](key_type&& __k);
      // _GLIBCXX_RESOLVE_LIB_DEFECTS
      // DR 761. unordered_map needs an at() member function.
      mapped_type&
      at(const key_type& __k);
      const mapped_type&
      at(const key_type& __k) const;
{% endhighlight %}
原来 \_Map\_base 是来提供 at 和 operator[] 的，好说，回过头看。

{% highlight cpp %}
  template<typename _Key, typename _Value, typename _Alloc,
           typename _ExtractKey, typename _Equal,
           typename _H1, typename _H2, typename _Hash,
           typename _RehashPolicy, typename _Traits,
           bool _Unique_keys = _Traits::__unique_keys::value>
    struct _Map_base { };
{% endhighlight %}

\_Map\_base 竟然有自己就直接给了个空实现，这是何必呢？后面其实是有 \_Unique\_keys true false 两种状况的特化的。不过注意到只有 map 是有 operator[] 和 at 的，set, multiset, multimap 都不提供。multi 会匹配到下面的特化：

{% highlight cpp %}
  template<typename _Key, typename _Pair, typename _Alloc, typename _Equal,
           typename _H1, typename _H2, typename _Hash,
           typename _RehashPolicy, typename _Traits>
    struct _Map_base<_Key, _Pair, _Alloc, _Select1st, _Equal,
                     _H1, _H2, _Hash, _RehashPolicy, _Traits, false>
    {
      using mapped_type = typename std::tuple_element<1, _Pair>::type;
    };
{% endhighlight %}

不过 set 呢？它也是 \_Unique\_Keys == true 的。注意看 std::tuple\_element，模板参数 \_Pair 上传进来的其实是 \_Value。也就是说，如果不是 pair 的话，就会 SFINAE，匹配回原来的那个空定义啦~。

接着来看后面 at 和 operator[] 的实现。

{% highlight cpp %}
    typename _Map_base<_Key, _Pair, _Alloc, _Select1st, _Equal,
                       _H1, _H2, _Hash, _RehashPolicy, _Traits, true>
                       ::mapped_type&
    _Map_base<_Key, _Pair, _Alloc, _Select1st, _Equal,
              _H1, _H2, _Hash, _RehashPolicy, _Traits, true>::
    operator[](const key_type& __k)
    {
      __hashtable* __h = static_cast<__hashtable*>(this);
      __hash_code __code = __h->_M_hash_code(__k);
      std::size_t __n = __h->_M_bucket_index(__k, __code);
      __node_type* __p = __h->_M_find_node(__n, __k, __code);
      if (!__p)
        {
          __p = __h->_M_allocate_node(std::piecewise_construct,
                                      std::tuple<const key_type&>(__k),
                                      std::tuple<>());
          return __h->_M_insert_unique_node(__n, __code, __p)->second;
        }
      return __p->_M_v().second;
    }
{% endhighlight %}

利用 CRTP，这里的 this 可以直接 cast 到 \_hashtable。然后便是计算 hash code 和拿 bucket index。`_M_find_node`， `_M_allocate_node`，`_M_insert_unqiue_node` 这些应该是其他的父类的接口，之前还没看到。at 的道理相同，只不不过不存在会直接 throw 掉。

\_Map\_base done。接下来是 \_Hashtable 的父类 \_Insert。

{% highlight cpp %}
  template<typename _Key, typename _Value, typename _Alloc,
           typename _ExtractKey, typename _Equal,
           typename _H1, typename _H2, typename _Hash,
           typename _RehashPolicy, typename _Traits,
           bool _Constant_iterators = _Traits::__constant_iterators::value,
           bool _Unique_keys = _Traits::__unique_keys::value>
    struct _Insert;
{% endhighlight %}

看来根据 \_Constant\_iterator 和 \_Unique\_keys 有特化。

{% highlight cpp %}
    struct _Insert<_Key, _Value, _Alloc, _ExtractKey, _Equal, _H1, _H2, _Hash,
                   _RehashPolicy, _Traits, true, true>
    : public _Insert_base<_Key, _Value, _Alloc, _ExtractKey, _Equal,
                           _H1, _H2, _Hash, _RehashPolicy, _Traits>
{% endhighlight %}

有一个父类 \_Insert\_base，父类里面都是外面通用的 insert。
{% highlight cpp %}
      __hashtable&
      _M_conjure_hashtable()
      { return *(static_cast<__hashtable*>(this)); }

      __ireturn_type
      insert(const value_type& __v)
      {
        __hashtable& __h = _M_conjure_hashtable();
        __node_gen_type __node_gen(__h);
        return __h._M_insert(__v, __node_gen, __unique_keys());
      }

      void
      _Insert_base<_Key, _Value, _Alloc, _ExtractKey, _Equal, _H1, _H2, _Hash,
                    _RehashPolicy, _Traits>::
      _M_insert_range(_InputIterator __first, _InputIterator __last,
                      const _NodeGetter& __node_gen)
      {
        using __rehash_type = typename __hashtable::__rehash_type;
        using __rehash_state = typename __hashtable::__rehash_state;
        using pair_type = std::pair<bool, std::size_t>;
        size_type __n_elt = __detail::__distance_fw(__first, __last);
        __hashtable& __h = _M_conjure_hashtable();
        __rehash_type& __rehash = __h._M_rehash_policy;
        const __rehash_state& __saved_state = __rehash._M_state();
        pair_type __do_rehash = __rehash._M_need_rehash(__h._M_bucket_count,
                                                        __h._M_element_count,
                                                        __n_elt);
        if (__do_rehash.first)
          __h._M_rehash(__do_rehash.second, __saved_state);
        for (; __first != __last; ++__first)
          __h._M_insert(*__first, __node_gen, __unique_keys());
      }
{% endhighlight %}

看来rehash 的时候有点 trick 啊，等会再去看。
子类应该是每种特化不同的 insert。

先看 \_Constant\_iterator 和 \_Unique\_keys 都是 true 的情况。
{% highlight cpp %}
      std::pair<iterator, bool>
      insert(value_type&& __v)
      {
        __hashtable& __h = this->_M_conjure_hashtable();
        __node_gen_type __node_gen(__h);
        return __h._M_insert(std::move(__v), __node_gen, __unique_keys());
      }
      iterator
      insert(const_iterator __hint, value_type&& __v)
      {
        __hashtable& __h = this->_M_conjure_hashtable();
        __node_gen_type __node_gen(__h);
        return __h._M_insert(__hint, std::move(__v), __node_gen,
                             __unique_keys());
      }
{% endhighlight %}

看来 insert 具体的实现应该在 \_Hashtable 里面，这里只是根据不同情况做转发。 \_Unique\_keys 是 false 的时候唯一的区别就是返回值  std::pair&lt;iterator, bool&gt; 变成了 iterator。

还有 \_Constant\_iterator 是 false 的情况，也就是为 map 准备的。
{% highlight cpp %}
      using __base_type::insert;
      template<typename _Pair>
        using __is_cons = std::is_constructible<value_type, _Pair&&>;
      template<typename _Pair>
        using _IFcons = std::enable_if<__is_cons<_Pair>::value>;
      template<typename _Pair>
        using _IFconsp = typename _IFcons<_Pair>::type;
      template<typename _Pair, typename = _IFconsp<_Pair>>
        __ireturn_type
        insert(_Pair&& __v)
        {
          __hashtable& __h = this->_M_conjure_hashtable();
          return __h._M_emplace(__unique_keys(), std::forward<_Pair>(__v));
        }
      template<typename _Pair, typename = _IFconsp<_Pair>>
        iterator
        insert(const_iterator __hint, _Pair&& __v)
        {
          __hashtable& __h = this->_M_conjure_hashtable();
          return __h._M_emplace(__hint, __unique_keys(),
                                std::forward<_Pair>(__v));
        }
{% endhighlight %}

map 要 insert rvalue 的时候就会尽量去 emplace（\_M\_emplace 和 \_M\_insert 一样都在 \_Hashtable 里面）。enable 的条件是 value 是 is\_constructible 的。

\_Insert 到此结束。\_Insert 是为了将不同情况下 insert 逻辑提取出来，针对 \_Unique\_keys，\_Constant\_iterator 做特化，而统一的 \_M\_insert 和 \_M\_emplace 则还是放在 \_Hashtable 本身中。

下一站是 \_Rehash\_base。
{% highlight cpp %}
  template<typename _Key, typename _Value, typename _Alloc,
           typename _ExtractKey, typename _Equal,
           typename _H1, typename _H2, typename _Hash,
           typename _RehashPolicy, typename _Traits>
    struct _Rehash_base;
  /// Specialization.
  template<typename _Key, typename _Value, typename _Alloc,
           typename _ExtractKey, typename _Equal,
           typename _H1, typename _H2, typename _Hash, typename _Traits>
    struct _Rehash_base<_Key, _Value, _Alloc, _ExtractKey, _Equal,
                        _H1, _H2, _Hash, _Prime_rehash_policy, _Traits>
    {
      using __hashtable = _Hashtable<_Key, _Value, _Alloc, _ExtractKey,
                                     _Equal, _H1, _H2, _Hash,
                                     _Prime_rehash_policy, _Traits>;
      float
      max_load_factor() const noexcept
      {
        const __hashtable* __this = static_cast<const __hashtable*>(this);
        return __this->__rehash_policy().max_load_factor();
      }
      void
      max_load_factor(float __z)
      {
        __hashtable* __this = static_cast<__hashtable*>(this);
        __this->__rehash_policy(_Prime_rehash_policy(__z));
      }
      void
      reserve(std::size_t __n)
      {
        __hashtable* __this = static_cast<__hashtable*>(this);
        __this->rehash(__builtin_ceil(__n / max_load_factor()));
      }
    };
{% endhighlight %}
针对默认情况下的 \_Prime\_rehash\_policy 做特化，提供 max\_load\_factor 和 reserve。既然到这里了，就直接去看一下 \_Prime\_rehash\_policy 是怎样的吧。

{% highlight cpp %}
  /// Default value for rehash policy. Bucket size is (usually) the
  /// smallest prime that keeps the load factor small enough.
  struct _Prime_rehash_policy
  {
    _Prime_rehash_policy(float __z = 1.0)
    : _M_max_load_factor(__z), _M_next_resize(0) { }
{% endhighlight %}

如果给定 max\_load\_factor 的话，会根据元素个数给你 bucket 个数
{% highlight cpp %}
    std::size_t
    _M_bkt_for_elements(std::size_t __n) const
    { return __builtin_ceil(__n / (long double)_M_max_load_factor); }
{% endhighlight %}

{% highlight cpp %}
    // Return a bucket size no smaller than n.
    std::size_t
    _M_next_bkt(std::size_t __n) const;

    std::pair<bool, std::size_t>
    _M_need_rehash(std::size_t __n_bkt, std::size_t __n_elt,
                   std::size_t __n_ins) const;
    typedef std::size_t _State;
    _State
    _M_state() const
    { return _M_next_resize; }
    void

    _M_reset() noexcept
    { _M_next_resize = 0; }
    void
    _M_reset(_State __state)
    { _M_next_resize = __state; }
    enum { _S_n_primes = sizeof(unsigned long) != 8 ? 256 : 256 + 48 };
    static const std::size_t _S_growth_factor = 2;
    float _M_max_load_factor;
    mutable std::size_t _M_next_resize;
  };
{% endhighlight %}
\_M\_next\_bkt，\_M\_need\_rehash 的实现在 `src/c++11/hashtable_c++0x.cc` 里面。

{% highlight cpp %}
  std::size_t
  _Prime_rehash_policy::_M_next_bkt(std::size_t __n) const
  {
    // Optimize lookups involving the first elements of __prime_list.
    // (useful to speed-up, eg, constructors)
    static const unsigned char __fast_bkt[12]
      = { 2, 2, 2, 3, 5, 5, 7, 7, 11, 11, 11, 11 };
    if (__n <= 11)
      {
        _M_next_resize =
          __builtin_ceil(__fast_bkt[__n] * (long double)_M_max_load_factor);
        return __fast_bkt[__n];
      }
    const unsigned long* __next_bkt =
      std::lower_bound(__prime_list + 5, __prime_list + _S_n_primes, __n);
    _M_next_resize =
      __builtin_ceil(*__next_bkt * (long double)_M_max_load_factor);
    return *__next_bkt;
  }
{% endhighlight %}

这里为内存访问做了个小优化，如果 \_\_n 比较小就先从 \_\_fast\_bkt 里面找素数，否则就从 \_\_prime\_list 里面下标为 [5, \_S\_n\_primes] 里面找一个 \_\_n 的 lower\_bound，来作为下次扩张的 bucket size，并且缓存了 \_M\_next\_resize 就是下次需要 resize 的界限。注意到 \_S\_n\_primes 这个 tricky 的常数，在sizeof(unsigned long) 的范围内给出了素数的间隔最大值。

{% highlight cpp %}
  std::pair<bool, std::size_t>
  _Prime_rehash_policy::
  _M_need_rehash(std::size_t __n_bkt, std::size_t __n_elt,
                 std::size_t __n_ins) const
  {
    if (__n_elt + __n_ins >= _M_next_resize)
      {
        long double __min_bkts = (__n_elt + __n_ins)
                                   / (long double)_M_max_load_factor;
        if (__min_bkts >= __n_bkt)
          return std::make_pair(true,
            _M_next_bkt(std::max<std::size_t>(__builtin_floor(__min_bkts) + 1,
                                              __n_bkt * _S_growth_factor)));
        _M_next_resize
          = __builtin_floor(__n_bkt * (long double)_M_max_load_factor);
        return std::make_pair(false, 0);
      }
    else
      return std::make_pair(false, 0);
  }
{% endhighlight %}

如果当前元素（\_\_n\_elt）和增加元素（\_\_n\_ins）的和超过了 \_M\_next\_resize 且超过了 \_M\_load\_factor 的容量，则会 return true，和新的 bucket 数量 = \_M\_next\_bkt(max(floor(\_\_min\_bkts) + 1, \_\_n\_bkt * 2))，还是从素数表里面 lookup。

注意看 \_M\_state，因为外界调用 \_M\_need\_rehash 会改变 \_M\_next\_resize，所以这个 state 需要外界在调用之前保留。

\_Rehash\_base 也搞定了，原来是在做 hashtable resize 时候确定大小的事情。

接下来是 \_Equality。为了节省滚动条长度，这里直接剧透掉好了。\_Equality 是为 \_Hashtable 提供 operator== 的，外面 unordered 容易就是通过调用 \_Equality::\_M\_equal 做是否相等的比较。对于 \_UniqueKeys == true，operator== 直接在一个 \_Hashtable 上遍历 iterator 两边做比较；对于 false 的情况，还会比较 Key 相等时是否是同一个排列。具体这里先不仔细研究，详情请看 [n3068](http://www.open-std.org/jtc1/sc22/wg21/docs/papers/2010/n3068.pdf)。

总算剩下一个 \_Hashtable\_alloc，扫一下好了。主要是关注 allocate\_node 和 allocate\_bucket 是怎么做的。

{% highlight cpp %}
  template<typename _NodeAlloc>
    template<typename... _Args>
      typename _Hashtable_alloc<_NodeAlloc>::__node_type*
      _Hashtable_alloc<_NodeAlloc>::_M_allocate_node(_Args&&... __args)
      {
        auto __nptr = __node_alloc_traits::allocate(_M_node_allocator(), 1);
        __node_type* __n = std::__addressof(*__nptr);
        __try
          {
            __value_alloc_type __a(_M_node_allocator());
            ::new ((void*)__n) __node_type;
            __value_alloc_traits::construct(__a, __n->_M_valptr(),
                                            std::forward<_Args>(__args)...);
            return __n;
          }
        __catch(...)
          {
            __node_alloc_traits::deallocate(_M_node_allocator(), __nptr, 1);
            __throw_exception_again;
          }
      }
{% endhighlight %}

恩。。。就是 allocate 一块 \_\_node\_type 区域，placement new，然后 construct 具体的 value。看来 \_\_node 是在外面做一些链接处理的。

注意看这个：
{% highlight cpp %}
  template<typename _NodeAlloc>
    void
    _Hashtable_alloc<_NodeAlloc>::_M_deallocate_nodes(__node_type* __n)
    {
      while (__n)
        {
          __node_type* __tmp = __n;
          __n = __n->_M_next();
          _M_deallocate_node(__tmp);
        }
    }
{% endhighlight %}
好吧，也就是说这些 node 其实是组成了一个 forward\_list。（ps. 为啥不直接用 forward\_list 呢）

{% highlight cpp %}
  template<typename _NodeAlloc>
    typename _Hashtable_alloc<_NodeAlloc>::__bucket_type*
    _Hashtable_alloc<_NodeAlloc>::_M_allocate_buckets(std::size_t __n)
    {
      __bucket_alloc_type __alloc(_M_node_allocator());
      auto __ptr = __bucket_alloc_traits::allocate(__alloc, __n);
      __bucket_type* __p = std::__addressof(*__ptr);
      __builtin_memset(__p, 0, __n * sizeof(__bucket_type));
      return __p;
    }
{% endhighlight %}
而对于 bucket，则是一块 \_\_bucket\_type 区域。

{% highlight cpp %}
      using __node_base = __detail::_Hash_node_base;
      using __bucket_type = __node_base*;
{% endhighlight %}

原来就是一堆 node 的指针，然后指向 bucket 中的第一个 node。

总算，基类都搞定了，可以看 \_Hashtable。前面都是一堆 using，对 base 做 alias，发现到这个：

{% highlight cpp %}
      using __reuse_or_alloc_node_type =
        __detail::_ReuseOrAllocNode<__node_alloc_type>;
{% endhighlight %}

好不错哟，这就是不想用 forward\_list 的原因嘛，自己 reuse node。

继续往下，挑重点看。
{% highlight cpp %}
      explicit
      _Hashtable(size_type __n = 10,
                 const _H1& __hf = _H1(),
                 const key_equal& __eql = key_equal(),
                 const allocator_type& __a = allocator_type())
      : _Hashtable(__n, __hf, _H2(), _Hash(), __eql,
                   __key_extract(), __a)
      { }

  template<typename _Key, typename _Value,
           typename _Alloc, typename _ExtractKey, typename _Equal,
           typename _H1, typename _H2, typename _Hash, typename _RehashPolicy,
           typename _Traits>
    _Hashtable<_Key, _Value, _Alloc, _ExtractKey, _Equal,
               _H1, _H2, _Hash, _RehashPolicy, _Traits>::
    _Hashtable(size_type __bucket_hint,
               const _H1& __h1, const _H2& __h2, const _Hash& __h,
               const _Equal& __eq, const _ExtractKey& __exk,
               const allocator_type& __a)
    : __hashtable_base(__exk, __h1, __h2, __h, __eq),
      __map_base(),
      __rehash_base(),
      __hashtable_alloc(__node_alloc_type(__a)),
      _M_element_count(0),
      _M_rehash_policy()
    {
      _M_bucket_count = _M_rehash_policy._M_next_bkt(__bucket_hint);
      _M_buckets = this->_M_allocate_buckets(_M_bucket_count);
    }
{% endhighlight %}

默认情况下给了 hint == 10，也就是 bucket\_size  是 11。继续往下，记得刚才 operator[] 会调 \_M\_insert。

{% highlight cpp %}
  template<typename _Key, typename _Value,
           typename _Alloc, typename _ExtractKey, typename _Equal,
           typename _H1, typename _H2, typename _Hash, typename _RehashPolicy,
           typename _Traits>
    template<typename _Arg, typename _NodeGenerator>
      std::pair<typename _Hashtable<_Key, _Value, _Alloc,
                                    _ExtractKey, _Equal, _H1,
                                    _H2, _Hash, _RehashPolicy,
                                    _Traits>::iterator, bool>
      _Hashtable<_Key, _Value, _Alloc, _ExtractKey, _Equal,
                 _H1, _H2, _Hash, _RehashPolicy, _Traits>::
      _M_insert(_Arg&& __v, const _NodeGenerator& __node_gen, std::true_type)
      {
        const key_type& __k = this->_M_extract()(__v);
        __hash_code __code = this->_M_hash_code(__k);
        size_type __bkt = _M_bucket_index(__k, __code);
        __node_type* __n = _M_find_node(__bkt, __k, __code);
        if (__n)
          return std::make_pair(iterator(__n), false);
        __n = __node_gen(std::forward<_Arg>(__v));
        return std::make_pair(_M_insert_unique_node(__bkt, __code, __n), true);
      }
{% endhighlight %}
这是 unqiue 的情况，如果原来的 node 存在就直接覆盖掉，如果不存在则抓发到 \_M\_insert\_unique\_node 上。因为要新添一个 node，所以要处理 size 是否够用是不是要 rehash 的情况。

{% highlight cpp %}
    _M_insert_unique_node(size_type __bkt, __hash_code __code,
                          __node_type* __node)
    {
      const __rehash_state& __saved_state = _M_rehash_policy._M_state();
      std::pair<bool, std::size_t> __do_rehash
        = _M_rehash_policy._M_need_rehash(_M_bucket_count, _M_element_count, 1);
      __try
        {
          if (__do_rehash.first)
            {
              _M_rehash(__do_rehash.second, __saved_state);
              __bkt = _M_bucket_index(this->_M_extract()(__node->_M_v()), __code);
            }
          this->_M_store_code(__node, __code);
          // Always insert at the beginning of the bucket.
          _M_insert_bucket_begin(__bkt, __node);
          ++_M_element_count;
          return iterator(__node);
        }
      __catch(...)
        {
          this->_M_deallocate_node(__node);
          __throw_exception_again;
        }
    }
{% endhighlight %}

插入时总是在 list 头。

{% highlight cpp %}
    _M_insert_bucket_begin(size_type __bkt, __node_type* __node)
    {
      if (_M_buckets[__bkt])
        {
          __node->_M_nxt = _M_buckets[__bkt]->_M_nxt;
          _M_buckets[__bkt]->_M_nxt = __node;
        }
      else
        {
          __node->_M_nxt = _M_before_begin._M_nxt;
          _M_before_begin._M_nxt = __node;
          if (__node->_M_nxt)
            _M_buckets[_M_bucket_index(__node->_M_next())] = __node;
          _M_buckets[__bkt] = &_M_before_begin;
        }
    }
{% endhighlight %}
如果 bucket 原来是空的那就直接扔进去，如果不是的话，还要在 \_M\_before\_begin 做一些操作。诶，看起来 \_M\_before\_begin 好像就是 iterator begin 的意思！\_M\_before\_begin.\_M\_nxt 就是每次拿到的 begin() ！

{% highlight cpp %}
      __node_type*
      _M_begin() const
      { return static_cast<__node_type*>(_M_before_begin._M_nxt); }

      iterator
      begin() noexcept
      { return iterator(_M_begin()); }
{% endhighlight %}

这样说来，每次在空的 bucket insert 都会把 begin 移到这个 bucket 上~~

似乎扯远了，继续回到 insert。
{% highlight cpp %}
      _M_insert(const_iterator __hint, _Arg&& __v,
                const _NodeGenerator& __node_gen,
                std::false_type)
      {
        // First compute the hash code so that we don't do anything if it
        // throws.
        __hash_code __code = this->_M_hash_code(this->_M_extract()(__v));
        // Second allocate new node so that we don't rehash if it throws.
        __node_type* __node = __node_gen(std::forward<_Arg>(__v));
        return _M_insert_multi_node(__hint._M_cur, __code, __node);
      }

    _M_insert_multi_node(__node_type* __hint, __hash_code __code,
                         __node_type* __node)
    {
      const __rehash_state& __saved_state = _M_rehash_policy._M_state();
      std::pair<bool, std::size_t> __do_rehash
        = _M_rehash_policy._M_need_rehash(_M_bucket_count, _M_element_count, 1);
      __try
        {
          if (__do_rehash.first)
            _M_rehash(__do_rehash.second, __saved_state);
          this->_M_store_code(__node, __code);
          const key_type& __k = this->_M_extract()(__node->_M_v());
          size_type __bkt = _M_bucket_index(__k, __code);
          __node_base* __prev
            = __builtin_expect(__hint != nullptr, false)
              && this->_M_equals(__k, __code, __hint)
                ? __hint
                : _M_find_before_node(__bkt, __k, __code);
          if (__prev)
            {
              __node->_M_nxt = __prev->_M_nxt;
              __prev->_M_nxt = __node;
              if (__builtin_expect(__prev == __hint, false))
                if (__node->_M_nxt
                    && !this->_M_equals(__k, __code, __node->_M_next()))
                  {
                    size_type __next_bkt = _M_bucket_index(__node->_M_next());
                    if (__next_bkt != __bkt)
                      _M_buckets[__next_bkt] = __node;
                  }
            }
          else
            _M_insert_bucket_begin(__bkt, __node);
          ++_M_element_count;
          return iterator(__node);
        }
      __catch(...)
        {
          this->_M_deallocate_node(__node);
          __throw_exception_again;
        }
    }
{% endhighlight %}

如果找到了 key 一样的 node 就插在他之前，否则的话就是正常 \_M\_insert\_bucket\_begin。hint 的用法就是拿来判断这个是不是直接就是相等的那个 key 的位置，如果是的话就不用再找了~。

看一下 \_M\_find\_before\_node
{% highlight cpp %}
      __node_base*
      _M_find_before_node(size_type, const key_type&, __hash_code) const;
      __node_type*
      _M_find_node(size_type __bkt, const key_type& __key,
                   __hash_code __c) const
      {
        __node_base* __before_n = _M_find_before_node(__bkt, __key, __c);
        if (__before_n)
          return static_cast<__node_type*>(__before_n->_M_nxt);
        return nullptr;
      }
{% endhighlight %}
原来之前 operator[] 和 at 的 \_M\_find\_node 也转到 \_M\_find\_before\_node 里了。

{% highlight cpp %}
    _M_find_before_node(size_type __n, const key_type& __k,
                        __hash_code __code) const
    {
      __node_base* __prev_p = _M_buckets[__n];
      if (!__prev_p)
        return nullptr;
      for (__node_type* __p = static_cast<__node_type*>(__prev_p->_M_nxt);;
           __p = __p->_M_next())
        {
          if (this->_M_equals(__k, __code, __p))
            return __prev_p;
          if (!__p->_M_nxt || _M_bucket_index(__p->_M_next()) != __n)
            break;
          __prev_p = __p;
        }
      return nullptr;
    }
{% endhighlight %}

恩，就是顺序查找，如果这个 bucket 里找不到的话就 return nullptr。\_Hastable::find 调用 \_M\_find\_node 就可以了~。

对了，之前一直没看 rehash 具体的实现，只是知道应该 rehash 到多大。

{% highlight cpp %}
    void
    _Hashtable<_Key, _Value, _Alloc, _ExtractKey, _Equal,
               _H1, _H2, _Hash, _RehashPolicy, _Traits>::
    _M_rehash(size_type __n, const __rehash_state& __state)
    {
      __try
        {
          _M_rehash_aux(__n, __unique_keys());
        }
      __catch(...)
        {
          // A failure here means that buckets allocation failed. We only
          // have to restore hash policy previous state.
          _M_rehash_policy._M_reset(__state);
          __throw_exception_again;
        }
    }
{% endhighlight %}

同样，\_M\_rehash\_aux 分为 unique 和 multi 两种。

{% highlight cpp %}
    void
    _Hashtable<_Key, _Value, _Alloc, _ExtractKey, _Equal,
               _H1, _H2, _Hash, _RehashPolicy, _Traits>::
    _M_rehash_aux(size_type __n, std::true_type)
    {
      __bucket_type* __new_buckets = this->_M_allocate_buckets(__n);
      __node_type* __p = _M_begin();
      _M_before_begin._M_nxt = nullptr;
      std::size_t __bbegin_bkt = 0;
      while (__p)
        {
          __node_type* __next = __p->_M_next();
          std::size_t __bkt = __hash_code_base::_M_bucket_index(__p, __n);
          if (!__new_buckets[__bkt])
            {
              __p->_M_nxt = _M_before_begin._M_nxt;
              _M_before_begin._M_nxt = __p;
              __new_buckets[__bkt] = &_M_before_begin;
              if (__p->_M_nxt)
                __new_buckets[__bbegin_bkt] = __p;
              __bbegin_bkt = __bkt;
            }
          else
            {
              __p->_M_nxt = __new_buckets[__bkt]->_M_nxt;
              __new_buckets[__bkt]->_M_nxt = __p;
            }
          __p = __next;
        }
      if (__builtin_expect(_M_bucket_count != 0, true))
        _M_deallocate_buckets();
      _M_bucket_count = __n;
      _M_buckets = __new_buckets;
    }
{% endhighlight %}

囧rz，其实完全可以调用 \_M\_insert 的。。。写代码真不嫌累。multi 版的 rehash 比较复杂，因为要保留之前相同 Key 元素之间的有序性，所以从前往后遍历时要向后插入，这时候必须 check next 指针是不是要更新（bucket 里面最后一个人的 next 指向另一个 bucket 的开始）。这里就不做分析了。

对了，之前有看到那个 node reuse，似乎一直没出现，在哪里呢？ 是在 operator= 的时候，因为本身要 clear，所以先把 node 留住，之后就可以复用了。operator= 的过程也非常繁琐（allocator propagate？），一样不表。

想一想还有什么？说一下 iterator 好了，之前指针指向的过程其实已经明了了，有一个 \_M\_before\_begin，而每次添加 node 的时候要把它指过去。那 local\_iterator 呢？只要 ++ 的时候判断是不是在同一个 bucket 就可以了。erase？也很简单，就是链表操作，要考虑 bucket 是否为空。\_Hashtable 基本就酱紫了。

对了还有，还没有看 hash 究竟是怎么 hash的呢。
bits/include/functional\_hash.h
{% highlight cpp %}
  template<typename _Result, typename _Arg>
    struct __hash_base
    {
      typedef _Result result_type;
      typedef _Arg argument_type;
    };
  /// Primary class template hash.
  template<typename _Tp>
    struct hash;
  /// Partial specializations for pointer types.
  template<typename _Tp>
    struct hash<_Tp*> : public __hash_base<size_t, _Tp*>
    {
      size_t
      operator()(_Tp* __p) const noexcept
      { return reinterpret_cast<size_t>(__p); }
    };
  // Explicit specializations for integer types.
#define _Cxx_hashtable_define_trivial_hash(_Tp) \
  template<> \
    struct hash<_Tp> : public __hash_base<size_t, _Tp> \
    { \
      size_t \
      operator()(_Tp __val) const noexcept \
      { return static_cast<size_t>(__val); } \
    };
{% endhighlight %}
后面你懂的，一大坨 \_Cxx\_hashtable\_define\_trivial\_hash(...) 。hash 你妹啊，其实就是自己嘛，也就是说 default 状态下 bucket 就是 value % bucket\_size。

而对于 double 和 float 呢，还有 string。

{% highlight cpp %}
  struct _Hash_impl
  {
    static size_t
    hash(const void* __ptr, size_t __clength,
         size_t __seed = static_cast<size_t>(0xc70f6907UL))
    { return _Hash_bytes(__ptr, __clength, __seed); }
    template<typename _Tp>
      static size_t
      hash(const _Tp& __val)
      { return hash(&__val, sizeof(__val)); }
    template<typename _Tp>
      static size_t
      __hash_combine(const _Tp& __val, size_t __hash)
      { return hash(&__val, sizeof(__val), __hash); }
  };

  template<>
    struct hash<float> : public __hash_base<size_t, float>
    {
      size_t
      operator()(float __val) const noexcept
      {
        // 0 and -0 both hash to zero.
        return __val != 0.0f ? std::_Hash_impl::hash(__val) : 0;
      }
    };
{% endhighlight %}

{% highlight cpp %}
  template<>
    struct hash<string>
    : public __hash_base<size_t, string>
    {
      size_t
      operator()(const string& __s) const noexcept
      { return std::_Hash_impl::hash(__s.data(), __s.length()); }
    };
{% endhighlight %}

用到了一个 magic number 0xc70f6907UL，应该是某种 hash 算法~。\_Hash\_bytes 则是在 libsupc++/hash\_bytes.cc

### 总结一下
1. 常见手法，把内部的实现扔到 detail namespace 里面
2. policy-based design，不过值得思考的是怎么增加复用性？注意到之前 \_M\_insert，\_M\_assign 等都有 multi 和 unique 两个版本。
3. CRTP，基类将功能进行分解，尽量做到类之间的功能正交。类模板设计接口，不同 policy 特化，编译器多态。
4. Hashtable 的实现就是 bucket vector 结合 node forward\_list，bucket size 总是素数，default == 11。size 不够用时会寻找下一个素数进行 rehash。
5. 排列比较 multi hashtable， 这个可以之后研究~ 