---
layout: post
title: "containers，inside std::deque"
description: "std::deque 在 libstdc++v3 中的实现解析。"
category: C++
tags: [C++, STL, code reading]
---
{% include JB/setup %}

继续 container ~ 来到 inlcude/bits/stl\_deque.h
假设我们对 deque 的内存布局一无所知，然后来看代码看看能不能看出蛛丝马迹。

{% highlight cpp %}
  /**
   * @brief This function controls the size of memory nodes.
   * @param __size The size of an element.
   * @return The number (not byte size) of elements per node.
   *
   * This function started off as a compiler kludge from SGI, but
   * seems to be a useful wrapper around a repeated constant
   * expression. The @b 512 is tunable (and no other code needs to
   * change), but no investigation has been done since inheriting the
   * SGI code. Touch _GLIBCXX_DEQUE_BUF_SIZE only if you know what
   * you are doing, however: changing it breaks the binary
   * compatibility!!
  */
#ifndef _GLIBCXX_DEQUE_BUF_SIZE
#define _GLIBCXX_DEQUE_BUF_SIZE 512
#endif
  inline size_t
  __deque_buf_size(size_t __size)
  { return (__size < _GLIBCXX_DEQUE_BUF_SIZE
            ? size_t(_GLIBCXX_DEQUE_BUF_SIZE / __size) : size_t(1)); }
{% endhighlight %}

<!--more-->

默认情况下一个 node 是 512 byte。 deque 是由多个 node 组成的？

继续往下看，是 deque iterator。

{% highlight cpp %}
  /**
   * @brief A deque::iterator.
   *
   * Quite a bit of intelligence here. Much of the functionality of
   * deque is actually passed off to this class. A deque holds two
   * of these internally, marking its valid range. Access to
   * elements is done as offsets of either of those two, relying on
   * operator overloading in this class.
   *
   * All the functions are op overloads except for _M_set_node.
  */
  template<typename _Tp, typename _Ref, typename _Ptr>
    struct _Deque_iterator
{% endhighlight %}

很奇怪的是，这里要三个模板参数。

{% highlight cpp %}
      typedef _Deque_iterator<_Tp, _Tp&, _Tp*> iterator;
      typedef _Deque_iterator<_Tp, const _Tp&, const _Tp*> const_iterator;
      static size_t _S_buffer_size() _GLIBCXX_NOEXCEPT
      { return __deque_buf_size(sizeof(_Tp)); }
      typedef std::random_access_iterator_tag iterator_category;
      typedef _Tp value_type;
      typedef _Ptr pointer;
      typedef _Ref reference;
      typedef size_t size_type;
      typedef ptrdiff_t difference_type;
      typedef _Tp** _Map_pointer;
      typedef _Deque_iterator _Self;
{% endhighlight %}

pointer 和 reference 是用模板参数来定义的，哦，可能外面是吧 deque 的 allocator 拿出来的 pointer 类型再给 iterator 可能是酱紫。ps, \_S\_buffer\_size 可以加一个 constexpr。还有一个 \_Map\_pointer 不知道做什么的。

{% highlight cpp %}
      _Tp* _M_cur;
      _Tp* _M_first;
      _Tp* _M_last;
      _Map_pointer _M_node;
{% endhighlight %}

\_M\_node 是 node 的指针，联想一下，deque 应该是由多块连续的内存区域组成（\_Tp array），还有一个 \_Tp* array 里面每个元素分别指向这些块，然后这个 \_M\_node 在这块区域上滑动表示当前位置。\_M\_cur 则是某个具体 \_Tp array 上的位置。当然，到目前位置，这些都是 yy。

{% highlight cpp %}
      _Deque_iterator(_Tp* __x, _Map_pointer __y) _GLIBCXX_NOEXCEPT
      : _M_cur(__x), _M_first(*__y),
        _M_last(*__y + _S_buffer_size()), _M_node(__y) { }
      _Deque_iterator() _GLIBCXX_NOEXCEPT
      : _M_cur(0), _M_first(0), _M_last(0), _M_node(0) { }
      _Deque_iterator(const iterator& __x) _GLIBCXX_NOEXCEPT
      : _M_cur(__x._M_cur), _M_first(__x._M_first),
        _M_last(__x._M_last), _M_node(__x._M_node) { }
{% endhighlight %}

构造没啥好看的，继续往下，又是各种 operator。哦还有之前遇到过的  \_M\_const\_cast。

{% highlight cpp %}
      iterator
      _M_const_cast() const _GLIBCXX_NOEXCEPT
      { return iterator(_M_cur, _M_node); }
{% endhighlight %}

重点来了

{% highlight cpp %}
      _Self&
      operator++() _GLIBCXX_NOEXCEPT
      {
        ++_M_cur;
        if (_M_cur == _M_last)
          {
            _M_set_node(_M_node + 1);
            _M_cur = _M_first;
          }
        return *this;
      }
      _Self
      operator++(int) _GLIBCXX_NOEXCEPT
      {
        _Self __tmp = *this;
        ++*this;
        return __tmp;
      }
{% endhighlight %}

看来大概是之前 yy 的那个原理。如果到这个 node 的末尾了，就换到下一个 node，然后 cur 放到这个 node 的起始。
\_M\_first 是一段 \_Tp 元素的第一个， \_M\_last 是一段 \_Tp 元素最后一个的位置 + 1（也就是无效的那个位置，其实应该命名为 end）。

{% highlight cpp %}
      /**
       * Prepares to traverse new_node. Sets everything except
       * _M_cur, which should therefore be set by the caller
       * immediately afterwards, based on _M_first and _M_last.
       */
      void
      _M_set_node(_Map_pointer __new_node) _GLIBCXX_NOEXCEPT
      {
        _M_node = __new_node;
        _M_first = *__new_node;
        _M_last = _M_first + difference_type(_S_buffer_size());
      }
{% endhighlight %}

不过这里有一个问题，如果 \_M\_set\_node 到头了呢？这里并没有做处理，难道是在外面。

{% highlight cpp %}
      _Self&
      operator--() _GLIBCXX_NOEXCEPT
      {
        if (_M_cur == _M_first)
          {
            _M_set_node(_M_node - 1);
            _M_cur = _M_last;
          }
        --_M_cur;
        return *this;
      }
      _Self
      operator--(int) _GLIBCXX_NOEXCEPT
      {
        _Self __tmp = *this;
        --*this;
        return __tmp;
      }
{% endhighlight %}

operator-- 也是，万一到了尽头？

{% highlight cpp %}
      _Self&
      operator+=(difference_type __n) _GLIBCXX_NOEXCEPT
      {
        const difference_type __offset = __n + (_M_cur - _M_first);
        if (__offset >= 0 && __offset < difference_type(_S_buffer_size()))
          _M_cur += __n;
        else
          {
            const difference_type __node_offset =
              __offset > 0 ? __offset / difference_type(_S_buffer_size())
                           : -difference_type((-__offset - 1)
                                              / _S_buffer_size()) - 1;
            _M_set_node(_M_node + __node_offset);
            _M_cur = _M_first + (__offset - __node_offset
                                 * difference_type(_S_buffer_size()));
          }
        return *this;
      }
      _Self
      operator+(difference_type __n) const _GLIBCXX_NOEXCEPT
      {
        _Self __tmp = *this;
        return __tmp += __n;
      }
{% endhighlight %}

如果 += \_\_n 不超过这个 buf，则直接前移，如果超过了，就除一下看有多少个。这段代码写的非常简洁~

{% highlight cpp %}
            const difference_type __node_offset =
              __offset > 0 ? __offset / difference_type(_S_buffer_size())
                           : -difference_type((-__offset - 1)
                                              / _S_buffer_size()) - 1;
            _M_set_node(_M_node + __node_offset);
            _M_cur = _M_first + (__offset - __node_offset
                                 * difference_type(_S_buffer_size())); 
{% endhighlight %}

注意这句喔 -difference\_type((-\_\_offset - 1)  / \_S\_buffer\_size()) - 1;
后面的 operator+ operator- operator-= 都是根据之前的 operator 定义的~。就不一一说明

后面还有各种比较 operator，还有 + - 什么的

{% highlight cpp %}
  template<typename _Tp, typename _Ref, typename _Ptr>
    inline typename _Deque_iterator<_Tp, _Ref, _Ptr>::difference_type
    operator-(const _Deque_iterator<_Tp, _Ref, _Ptr>& __x,
              const _Deque_iterator<_Tp, _Ref, _Ptr>& __y) _GLIBCXX_NOEXCEPT
    {
      return typename _Deque_iterator<_Tp, _Ref, _Ptr>::difference_type
        (_Deque_iterator<_Tp, _Ref, _Ptr>::_S_buffer_size())
        * (__x._M_node - __y._M_node - 1) + (__x._M_cur - __x._M_first)
        + (__y._M_last - __y._M_cur);
    }
  template<typename _Tp, typename _RefL, typename _PtrL,
           typename _RefR, typename _PtrR>
    inline typename _Deque_iterator<_Tp, _RefL, _PtrL>::difference_type
    operator-(const _Deque_iterator<_Tp, _RefL, _PtrL>& __x,
              const _Deque_iterator<_Tp, _RefR, _PtrR>& __y) _GLIBCXX_NOEXCEPT
    {
      return typename _Deque_iterator<_Tp, _RefL, _PtrL>::difference_type
        (_Deque_iterator<_Tp, _RefL, _PtrL>::_S_buffer_size())
        * (__x._M_node - __y._M_node - 1) + (__x._M_cur - __x._M_first)
        + (__y._M_last - __y._M_cur);
    }
  template<typename _Tp, typename _Ref, typename _Ptr>
    inline _Deque_iterator<_Tp, _Ref, _Ptr>
    operator+(ptrdiff_t __n, const _Deque_iterator<_Tp, _Ref, _Ptr>& __x)
    _GLIBCXX_NOEXCEPT
    { return __x + __n; }

{% endhighlight %}
都是一眼都能看懂的~

注意到下面还有一堆的 copy, fill ,copy\_backward, move, move\_backward 的重载。暂且不看，具体的实现都在 deque.tcc 里面。

接下来是 \_Deque\_base，目测和 \_Vector\_base 一个套路，只负责内存的分配。

{% highlight cpp %}
    class _Deque_base
    {
    public:
      typedef _Alloc allocator_type;
      allocator_type
      get_allocator() const _GLIBCXX_NOEXCEPT
      { return allocator_type(_M_get_Tp_allocator()); }
      typedef _Deque_iterator<_Tp, _Tp&, _Tp*> iterator;
      typedef _Deque_iterator<_Tp, const _Tp&, const _Tp*> const_iterator;
      _Deque_base()
      : _M_impl()
      { _M_initialize_map(0); }
      _Deque_base(size_t __num_elements)
      : _M_impl()
      { _M_initialize_map(__num_elements); }
      _Deque_base(const allocator_type& __a, size_t __num_elements)
      : _M_impl(__a)
      { _M_initialize_map(__num_elements); }
      _Deque_base(const allocator_type& __a)
      : _M_impl(__a)
      { }
#if __cplusplus >= 201103L
      _Deque_base(_Deque_base&& __x)
      : _M_impl(std::move(__x._M_get_Tp_allocator()))
      {
        _M_initialize_map(0);
        if (__x._M_impl._M_map)
          {
            std::swap(this->_M_impl._M_start, __x._M_impl._M_start);
            std::swap(this->_M_impl._M_finish, __x._M_impl._M_finish);
            std::swap(this->_M_impl._M_map, __x._M_impl._M_map);
            std::swap(this->_M_impl._M_map_size, __x._M_impl._M_map_size);
          }
      }
#endif
{% endhighlight %}

这里还是用了一个 \_M\_impl 成员，目测又继承了 allocator。\_M\_impl 里面有几个关键的成员，\_M\_start, \_M\_finish, \_M\_map, M\_map\_size。

{% highlight cpp %}
      struct _Deque_impl
      : public _Tp_alloc_type
      {
        _Tp** _M_map;
        size_t _M_map_size;
        iterator _M_start;
        iterator _M_finish;
{% endhighlight %}

\_M\_map 应该就是那段储存各个 node 地址的地方，\_M\_start, \_M\_finish 应该分别是 deque 的 start 和 finish。

{% highlight cpp %}
    protected:
      typedef typename _Alloc::template rebind<_Tp*>::other _Map_alloc_type;
      typedef typename _Alloc::template rebind<_Tp>::other _Tp_alloc_type;
{% endhighlight %}

在 \_Deque\_impl 中，为了分配 map，要得到一个 rebind 到 \_Tp* 的 allocator。

来看 \_M\_initialize\_map， \_M\_map 是怎么做初始化的。

{% highlight cpp %}
  template<typename _Tp, typename _Alloc>
    void
    _Deque_base<_Tp, _Alloc>::
    _M_initialize_map(size_t __num_elements)
    {
      const size_t __num_nodes = (__num_elements/ __deque_buf_size(sizeof(_Tp))
                                  + 1);
      this->_M_impl._M_map_size = std::max((size_t) _S_initial_map_size,
                                           size_t(__num_nodes + 2));
      this->_M_impl._M_map = _M_allocate_map(this->_M_impl._M_map_size);
      // For "small" maps (needing less than _M_map_size nodes), allocation
      // starts in the middle elements and grows outwards. So nstart may be
      // the beginning of _M_map, but for small maps it may be as far in as
      // _M_map+3.
      _Tp** __nstart = (this->_M_impl._M_map
                        + (this->_M_impl._M_map_size - __num_nodes) / 2);
      _Tp** __nfinish = __nstart + __num_nodes;
      __try
        { _M_create_nodes(__nstart, __nfinish); }
      __catch(...)
        {
          _M_deallocate_map(this->_M_impl._M_map, this->_M_impl._M_map_size);
          this->_M_impl._M_map = 0;
          this->_M_impl._M_map_size = 0;
          __throw_exception_again;
        }
      this->_M_impl._M_start._M_set_node(__nstart);
      this->_M_impl._M_finish._M_set_node(__nfinish - 1);
      this->_M_impl._M_start._M_cur = _M_impl._M_start._M_first;
      this->_M_impl._M_finish._M_cur = (this->_M_impl._M_finish._M_first
                                        + __num_elements
                                        % __deque_buf_size(sizeof(_Tp)));

{% endhighlight %}

如果传进来的是 0 的话，则 \_M\_map\_size 就是 enum { \_S\_initial\_map\_size = 8 }; ，\_\_nstart 被设成 中间的那个 node，\_\_nfinish 则是 (M\_map\_size + \_\_num\_nodes) / 2 的位置（根据之前的 max 这个位置肯定是有效的）。接着在这个范围上 create nodes。如果成功的话，\_M\_start 就会被 set 成这个 \_\_nstart，而 \_\_M\_finish 则会被 set 成 \_\_nfinish - 1（注意 \_\_nfinish - \_\_nstart == \_\_num\_nodes）。现在 \_\_M\_start 和 \_M\_finish 之间有 \_\_deque\_buf\_size * (\_\_num\_nodes - 1) 个元素，而 \_\_num\_nodes =  (\_\_num\_elements/ \_\_deque\_buf\_size+ 1);。如果现在把 \_M\_start.\_M\_cur 设成 \_M\_start.\_M\_first ，向后推 \_\_num\_elements 得到 \_M\_finish 所在的 node，再加上 \_\_num\_elements % \_\_deque\_buf\_size，就是 \_M\_finish.\_M\_cur 应该所在的位置~~~ 这就这段代码的含义。


来一张 deque 的直观图吧～。

![deque]({{ BASE_PATH }}/assets/deque.png)

顺便过一下 allocate 和 deallocate，不过大概都 yy 的到~~
{% highlight cpp %}
      _Tp**
      _M_allocate_map(size_t __n)
      { return _M_get_map_allocator().allocate(__n); }
      void
      _M_deallocate_map(_Tp** __p, size_t __n) _GLIBCXX_NOEXCEPT
      { _M_get_map_allocator().deallocate(__p, __n); }
{% endhighlight %}

\_M\_create\_nodes 应该就是在 map 上对每个 node 分配内存吧

{% highlight cpp %}
  template<typename _Tp, typename _Alloc>
    void
    _Deque_base<_Tp, _Alloc>::
    _M_create_nodes(_Tp** __nstart, _Tp** __nfinish)
    {
      _Tp** __cur;
      __try
        {
          for (__cur = __nstart; __cur < __nfinish; ++__cur)
            *__cur = this->_M_allocate_node();
        }
      __catch(...)
        {
          _M_destroy_nodes(__nstart, __cur);
          __throw_exception_again;
        }
    }

  template<typename _Tp, typename _Alloc>
    void
    _Deque_base<_Tp, _Alloc>::
    _M_destroy_nodes(_Tp** __nstart, _Tp** __nfinish) _GLIBCXX_NOEXCEPT
    {
      for (_Tp** __n = __nstart; __n < __nfinish; ++__n)
        _M_deallocate_node(*__n);
    }
{% endhighlight %}

这个错误处理做的好疼~~~ 。

接下来就是 deque 的正文了

{% highlight cpp %}
  template<typename _Tp, typename _Alloc = std::allocator<_Tp> >
    class deque : protected _Deque_base<_Tp, _Alloc>
{% endhighlight %}

大多的 ctor 都不用看，猜都猜的到，

{% highlight cpp %}
      explicit
      deque(size_type __n)
      : _Base(__n)
      { _M_default_initialize(); }
{% endhighlight %}

来看 default\_init

{% highlight cpp %}
#if __cplusplus >= 201103L
  template <typename _Tp, typename _Alloc>
    void
    deque<_Tp, _Alloc>::
    _M_default_initialize()
    {
      _Map_pointer __cur;
      __try
        {
          for (__cur = this->_M_impl._M_start._M_node;
               __cur < this->_M_impl._M_finish._M_node;
               ++__cur)
            std::__uninitialized_default_a(*__cur, *__cur + _S_buffer_size(),
                                           _M_get_Tp_allocator());
          std::__uninitialized_default_a(this->_M_impl._M_finish._M_first,
                                         this->_M_impl._M_finish._M_cur,
                                         _M_get_Tp_allocator());
        }
      __catch(...)
        {
          std::_Destroy(this->_M_impl._M_start, iterator(*__cur, __cur),
                        _M_get_Tp_allocator());
          __throw_exception_again;
        }
    }
#endif
{% endhighlight %}

跟 vector 的道理都一样，尽量不想去调你的构造函数~~。下面的 fill 也是同理

{% highlight cpp %}
  template <typename _Tp, typename _Alloc>
    void
    deque<_Tp, _Alloc>::
    _M_fill_initialize(const value_type& __value)
    {
      _Map_pointer __cur;
      __try
        {
          for (__cur = this->_M_impl._M_start._M_node;
               __cur < this->_M_impl._M_finish._M_node;
               ++__cur)
            std::__uninitialized_fill_a(*__cur, *__cur + _S_buffer_size(),
                                        __value, _M_get_Tp_allocator());
          std::__uninitialized_fill_a(this->_M_impl._M_finish._M_first,
                                      this->_M_impl._M_finish._M_cur,
                                      __value, _M_get_Tp_allocator());
        }
      __catch(...)
        {
          std::_Destroy(this->_M_impl._M_start, iterator(*__cur, __cur),
                        _M_get_Tp_allocator());
          __throw_exception_again;
        }
    }
{% endhighlight %}

析构基本也是同理。其他很多东西跟 vector， string 里面的都差不多。我比较关心 deque 什么时候会增长，以多大的幅度增长。

{% highlight cpp %}
      void
      push_back(const value_type& __x)
      {
        if (this->_M_impl._M_finish._M_cur
            != this->_M_impl._M_finish._M_last - 1)
          {
            this->_M_impl.construct(this->_M_impl._M_finish._M_cur, __x);
            ++this->_M_impl._M_finish._M_cur;
          }
        else
          _M_push_back_aux(__x);
      }
{% endhighlight %}

如果到达了这个 node 最后一个位置的话，就会 call 到下面。

{% highlight cpp %}
  // Called only if _M_impl._M_finish._M_cur == _M_impl._M_finish._M_last - 1.
  template<typename _Tp, typename _Alloc>
    template<typename... _Args>
      void
      deque<_Tp, _Alloc>::
      _M_push_back_aux(_Args&&... __args)
      {
        _M_reserve_map_at_back();
        *(this->_M_impl._M_finish._M_node + 1) = this->_M_allocate_node();
        __try
          {
            this->_M_impl.construct(this->_M_impl._M_finish._M_cur,
                                    std::forward<_Args>(__args)...);
            this->_M_impl._M_finish._M_set_node(this->_M_impl._M_finish._M_node
                                                + 1);
            this->_M_impl._M_finish._M_cur = this->_M_impl._M_finish._M_first;
          }
        __catch(...)
          {
            _M_deallocate_node(*(this->_M_impl._M_finish._M_node + 1));
            __throw_exception_again;
          }
      }
{% endhighlight %}

\_M\_reserve\_map\_at\_back 之后进行了 \_M\_allocate\_node，关键在 \_M\_reserve\_map\_at\_back 里面

{% highlight cpp %}
      void
      _M_reserve_map_at_back(size_type __nodes_to_add = 1)
      {
        if (__nodes_to_add + 1 > this->_M_impl._M_map_size
            - (this->_M_impl._M_finish._M_node - this->_M_impl._M_map))
          _M_reallocate_map(__nodes_to_add, false);
      }
{% endhighlight %}

如果 map 真的到头的话，就 reallocate map，相应的后面也有 front 的处理

{% highlight cpp %}
      void
      _M_reserve_map_at_front(size_type __nodes_to_add = 1)
      {
        if (__nodes_to_add > size_type(this->_M_impl._M_start._M_node
                                       - this->_M_impl._M_map))
          _M_reallocate_map(__nodes_to_add, true);
      }
{% endhighlight %}

来看一下 \_M\_reallocate\_map 是怎么做的吧

{% highlight cpp %}
  template <typename _Tp, typename _Alloc>
    void
    deque<_Tp, _Alloc>::
    _M_reallocate_map(size_type __nodes_to_add, bool __add_at_front)
    {
      const size_type __old_num_nodes
        = this->_M_impl._M_finish._M_node - this->_M_impl._M_start._M_node + 1;
      const size_type __new_num_nodes = __old_num_nodes + __nodes_to_add;
      _Map_pointer __new_nstart;
      if (this->_M_impl._M_map_size > 2 * __new_num_nodes)
        {
          __new_nstart = this->_M_impl._M_map + (this->_M_impl._M_map_size
                                         - __new_num_nodes) / 2
                         + (__add_at_front ? __nodes_to_add : 0);
          if (__new_nstart < this->_M_impl._M_start._M_node)
            std::copy(this->_M_impl._M_start._M_node,
                      this->_M_impl._M_finish._M_node + 1,
                      __new_nstart);
          else
            std::copy_backward(this->_M_impl._M_start._M_node,
                               this->_M_impl._M_finish._M_node + 1,
                               __new_nstart + __old_num_nodes);
        }
      else
{% endhighlight %}

目测还是按两倍来的呢~ 如果当前的 size &gt; new\_num\_nodes，则会吧 start 重新定位到 \_M\_map\_size   - \_\_new\_num\_nodes) / 2 的位置上，如果是 add\_to\_front 再往前移 \_\_nodes\_to\_add 个坑。接着就是 copy 了，注意这里是有 overlap 了，所以做判断用 copy 还是 copy\_backward。

而如果当前 size &lt; new\_num\_nodes，则会按照近乎两倍的大小进行分配，设置 new\_start 的方法跟之前大概相似。

说到这里，deque 会自己 shrink 么？我们来看 pop。

{% highlight cpp %}
      void
      pop_front() _GLIBCXX_NOEXCEPT
      {
        if (this->_M_impl._M_start._M_cur
            != this->_M_impl._M_start._M_last - 1)
          {
            this->_M_impl.destroy(this->_M_impl._M_start._M_cur);
            ++this->_M_impl._M_start._M_cur;
          }
        else
          _M_pop_front_aux();
      }
{% endhighlight %}

{% highlight cpp %}
  template <typename _Tp, typename _Alloc>
    void deque<_Tp, _Alloc>::
    _M_pop_front_aux()
    {
      this->_M_impl.destroy(this->_M_impl._M_start._M_cur);
      _M_deallocate_node(this->_M_impl._M_start._M_first);
      this->_M_impl._M_start._M_set_node(this->_M_impl._M_start._M_node + 1);
      this->_M_impl._M_start._M_cur = this->_M_impl._M_start._M_first;
    }
{% endhighlight %}

如果 \_M\_cur == \_M\_last - 1，也就是 pop 到了这个 node 的尾巴，就会 deallocate 掉然后换下一个 node。
大概的原理都清楚了，那我们随意的往下看好了~

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
          typedef typename std::__is_integer<_InputIterator>::__type _Integral;
          _M_assign_dispatch(__first, __last, _Integral());
        }
#endif
{% endhighlight %}

然后是 dispatch 

{% highlight cpp %}
      template<typename _Integer>
        void
        _M_assign_dispatch(_Integer __n, _Integer __val, __true_type)
        { _M_fill_assign(__n, __val); }
      // called by the range assign to implement [23.1.1]/9
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

{% highlight cpp %}
      void
      _M_fill_assign(size_type __n, const value_type& __val)
      {
        if (__n > size())
          {
            std::fill(begin(), end(), __val);
            insert(end(), __n - size(), __val);
          }
        else
          {
            _M_erase_at_end(begin() + difference_type(__n));
            std::fill(begin(), end(), __val);
          }
      }
{% endhighlight %}

\_M\_fill\_assign 会直接去调 std fill，不够的后面都 insert，而如果多余的话就 \_M\_erase\_at\_end。

{% highlight cpp %}
      void
      _M_erase_at_end(iterator __pos)
      {
        _M_destroy_data(__pos, end(), _M_get_Tp_allocator());
        _M_destroy_nodes(__pos._M_node + 1,
                         this->_M_impl._M_finish._M_node + 1);
        this->_M_impl._M_finish = __pos;
      }
{% endhighlight %}

\_M\_assign\_aux 也是类似的原理

{% highlight cpp %}
  template <typename _Tp, class _Alloc>
    template <typename _InputIterator>
      void
      deque<_Tp, _Alloc>::
      _M_assign_aux(_InputIterator __first, _InputIterator __last,
                    std::input_iterator_tag)
      {
        iterator __cur = begin();
        for (; __first != __last && __cur != end(); ++__cur, ++__first)
          *__cur = *__first;
        if (__first == __last)
          _M_erase_at_end(__cur);
        else
          insert(end(), __first, __last);
      }
{% endhighlight %}

换个心情看看小函数，比如说 operator\[\]，其实直接拿 iterator 来做就好了。

{% highlight cpp %}
      reference
      operator[](size_type __n) _GLIBCXX_NOEXCEPT
      { return this->_M_impl._M_start[difference_type(__n)]; }
{% endhighlight %}

再比如说 shrink\_to\_fit

{% highlight cpp %}
      void
      shrink_to_fit() noexcept
      { _M_shrink_to_fit(); }
{% endhighlight %}

{% highlight cpp %}
  template <typename _Tp, typename _Alloc>
    bool
    deque<_Tp, _Alloc>::
    _M_shrink_to_fit()
    {
      const difference_type __front_capacity
        = (this->_M_impl._M_start._M_cur - this->_M_impl._M_start._M_first);
      if (__front_capacity == 0)
        return false;
      const difference_type __back_capacity
        = (this->_M_impl._M_finish._M_last - this->_M_impl._M_finish._M_cur);
      if (__front_capacity + __back_capacity < _S_buffer_size())
        return false;
      return std::__shrink_to_fit_aux<deque>::_S_do_it(*this);
    }
{% endhighlight %}

之前看过，其实里面就是用 swap 的那个方法。如果 front\_capacity == 0 或者 back\_capacity + front\_capacity 还不到一个 buffer size 的时候是不会 swap 的~。

再看 resize
{% highlight cpp %}
      void
      resize(size_type __new_size, const value_type& __x)
      {
        const size_type __len = size();
        if (__new_size > __len)
          insert(this->_M_impl._M_finish, __new_size - __len, __x);
        else if (__new_size < __len)
          _M_erase_at_end(this->_M_impl._M_start
                          + difference_type(__new_size));
      }
{% endhighlight %}

没什么新内容，insert 一直没看。insert 有好几个重载，一个一个来。

{% highlight cpp %}
      iterator
      insert(const_iterator __position, value_type&& __x)
      { return emplace(__position, std::move(__x)); }
{% endhighlight %}

{% highlight cpp %}
  template<typename _Tp, typename _Alloc>
    template<typename... _Args>
      typename deque<_Tp, _Alloc>::iterator
      deque<_Tp, _Alloc>::
      emplace(const_iterator __position, _Args&&... __args)
      {
        if (__position._M_cur == this->_M_impl._M_start._M_cur)
          {
            emplace_front(std::forward<_Args>(__args)...);
            return this->_M_impl._M_start;
          }
        else if (__position._M_cur == this->_M_impl._M_finish._M_cur)
          {
            emplace_back(std::forward<_Args>(__args)...);
            iterator __tmp = this->_M_impl._M_finish;
            --__tmp;
            return __tmp;
          }
        else
          return _M_insert_aux(__position._M_const_cast(),
                               std::forward<_Args>(__args)...);
      }
{% endhighlight %}

对 front 和 back 两种情况作了特殊处理，不过如果不是这两种情况，就疼了吧

{% highlight cpp %}
    template<typename... _Args>
      typename deque<_Tp, _Alloc>::iterator
      deque<_Tp, _Alloc>::
      _M_insert_aux(iterator __pos, _Args&&... __args)
      {
        value_type __x_copy(std::forward<_Args>(__args)...); // XXX copy
        difference_type __index = __pos - this->_M_impl._M_start;
        if (static_cast<size_type>(__index) < size() / 2)
          {
            push_front(_GLIBCXX_MOVE(front()));
            iterator __front1 = this->_M_impl._M_start;
            ++__front1;
            iterator __front2 = __front1;
            ++__front2;
            __pos = this->_M_impl._M_start + __index;
            iterator __pos1 = __pos;
            ++__pos1;
            _GLIBCXX_MOVE3(__front2, __pos1, __front1);
          }
        else
          {
            push_back(_GLIBCXX_MOVE(back()));
            iterator __back1 = this->_M_impl._M_finish;
            --__back1;
            iterator __back2 = __back1;
            --__back2;
            __pos = this->_M_impl._M_start + __index;
            _GLIBCXX_MOVE_BACKWARD3(__pos, __back2, __back1);
          }
        *__pos = _GLIBCXX_MOVE(__x_copy);
        return __pos;
      }
{% endhighlight %}

看起来非常蛋疼。。。分别根据位置，选择 move 前半段还是后半段。最后调了 std::move。（这里省去了 \_\_cplusplus 的宏）。类似的，可以联想 insert n 个情况，insert range 和 erase 的实现。

= = 这种代码真的太容易看腻了。不过都是非常好的练习。

顺便，之前有一些全局的重载没有看，顺路观赏一下。

{% highlight cpp %}
  template<typename _Tp>
    _Deque_iterator<_Tp, _Tp&, _Tp*>
    copy(_Deque_iterator<_Tp, const _Tp&, const _Tp*> __first,
         _Deque_iterator<_Tp, const _Tp&, const _Tp*> __last,
         _Deque_iterator<_Tp, _Tp&, _Tp*> __result)
    {
      typedef typename _Deque_iterator<_Tp, _Tp&, _Tp*>::_Self _Self;
      typedef typename _Self::difference_type difference_type;
      difference_type __len = __last - __first;
      while (__len > 0)
        {
          const difference_type __clen
            = std::min(__len, std::min(__first._M_last - __first._M_cur,
                                       __result._M_last - __result._M_cur));
          std::copy(__first._M_cur, __first._M_cur + __clen, __result._M_cur);
          __first += __clen;
          __result += __clen;
          __len -= __clen;
        }
      return __result;
    }
{% endhighlight %}

具体重载里面还是调用 std 里面的东西，不过里面就是具体的  \_Tp* array copy 了。

比较麻烦的是 copy\_backward

{% highlight cpp %}
  template<typename _Tp>
    _Deque_iterator<_Tp, _Tp&, _Tp*>
    copy_backward(_Deque_iterator<_Tp, const _Tp&, const _Tp*> __first,
                  _Deque_iterator<_Tp, const _Tp&, const _Tp*> __last,
                  _Deque_iterator<_Tp, _Tp&, _Tp*> __result)
    {
      typedef typename _Deque_iterator<_Tp, _Tp&, _Tp*>::_Self _Self;
      typedef typename _Self::difference_type difference_type;
      difference_type __len = __last - __first;
      while (__len > 0)
        {
          difference_type __llen = __last._M_cur - __last._M_first;
          _Tp* __lend = __last._M_cur;
          difference_type __rlen = __result._M_cur - __result._M_first;
          _Tp* __rend = __result._M_cur;
          if (!__llen)
            {
              __llen = _Self::_S_buffer_size();
              __lend = *(__last._M_node - 1) + __llen;
            }
          if (!__rlen)
            {
              __rlen = _Self::_S_buffer_size();
              __rend = *(__result._M_node - 1) + __rlen;
            }
          const difference_type __clen = std::min(__len,
                                                  std::min(__llen, __rlen));
          std::copy_backward(__lend - __clen, __lend, __rend);
          __last -= __clen;
          __result -= __clen;
          __len -= __clen;
        }
      return __result;
    }
{% endhighlight %}

deque 就烂到这里好了，大概原理基本都已经明了了~

### 总结一下~~
感觉 STL 里面数据结构实现是很好的基本练习啊~ 比如说实现 insert，怎样保证正确性，整洁以及效率。