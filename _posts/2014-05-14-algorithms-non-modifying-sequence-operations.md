---
layout: post
title: "Algorithms 之 Non-modifying sequence operations"
description: ""
category: C++
tags: [C++, STL, code reading, algorithm]
---
{% include JB/setup %}
似乎有趣的东西并不多了，今天开始刷 [algorithms](http://en.cppreference.com/w/cpp/algorithm) 。先从最简单的开始，Non-modifying sequence operations，基本上都是在两个 iterator 之间做一些查找工作。

都是满满的编程练习题啊。

先看三个简单的，`all_of`，`any_of`，`none_of`。
{% highlight cpp %}
  template<typename _InputIterator, typename _Predicate>
    inline bool
    all_of(_InputIterator __first, _InputIterator __last, _Predicate __pred)
    { return __last == std::find_if_not(__first, __last, __pred); }

  template<typename _InputIterator, typename _Predicate>
    inline bool
    none_of(_InputIterator __first, _InputIterator __last, _Predicate __pred)
    { return __last == _GLIBCXX_STD_A::find_if(__first, __last, __pred); }

  template<typename _InputIterator, typename _Predicate>
    inline bool
    any_of(_InputIterator __first, _InputIterator __last, _Predicate __pred)
    { return !std::none_of(__first, __last, __pred); }
{% endhighlight %}

<!--more-->
功能都转到了 find 类的函数。find 一共有三个，`find`，`find_if`，`find_if_not`。他们应该都可以划归到 `find_if` 上，`find`  是 `find_if` 一个 equal functor，而 `find_if_not` 则是 `find_if` 一个 negative equal functor。

{% highlight cpp %}
  template<typename _InputIterator, typename _Tp>
    inline _InputIterator
    find(_InputIterator __first, _InputIterator __last,
         const _Tp& __val)
    {
      // concept requirements
      __glibcxx_function_requires(_InputIteratorConcept<_InputIterator>)
      __glibcxx_function_requires(_EqualOpConcept<
                typename iterator_traits<_InputIterator>::value_type, _Tp>)
      __glibcxx_requires_valid_range(__first, __last);
      return std::__find_if(__first, __last,
                            __gnu_cxx::__ops::__iter_equals_val(__val));
    }

  template<typename _InputIterator, typename _Predicate>
    inline _InputIterator
    find_if(_InputIterator __first, _InputIterator __last,
            _Predicate __pred)
    {
      // concept requirements
      __glibcxx_function_requires(_InputIteratorConcept<_InputIterator>)
      __glibcxx_function_requires(_UnaryPredicateConcept<_Predicate,
              typename iterator_traits<_InputIterator>::value_type>)
      __glibcxx_requires_valid_range(__first, __last);
      return std::__find_if(__first, __last,
                            __gnu_cxx::__ops::__pred_iter(__pred));
    }

  template<typename _InputIterator, typename _Predicate>
    inline _InputIterator
    find_if_not(_InputIterator __first, _InputIterator __last,
                _Predicate __pred)
    {
      // concept requirements
      __glibcxx_function_requires(_InputIteratorConcept<_InputIterator>)
      __glibcxx_function_requires(_UnaryPredicateConcept<_Predicate,
              typename iterator_traits<_InputIterator>::value_type>)
      __glibcxx_requires_valid_range(__first, __last);
      return std::__find_if_not(__first, __last,
                                __gnu_cxx::__ops::__pred_iter(__pred));
    }
{% endhighlight %}
只是多加了 concept check。内部都用 `__find_if` 和 `__find_if_not` 来做的。`__gnu_cxx::__ops` 就是对 functor 的一层封装，看名字 yy 就可以。

{% highlight cpp %}
  template<typename _Iterator, typename _Predicate>
    inline _Iterator
    __find_if(_Iterator __first, _Iterator __last, _Predicate __pred)
    {
      return __find_if(__first, __last, __pred,
                       std::__iterator_category(__first));
    }
  /// Provided for stable_partition to use.
  template<typename _InputIterator, typename _Predicate>
    inline _InputIterator
    __find_if_not(_InputIterator __first, _InputIterator __last,
                  _Predicate __pred)
    {
      return std::__find_if(__first, __last,
                            __gnu_cxx::__ops::__negate(__pred),
                            std::__iterator_category(__first));
    }
{% endhighlight %}

最后殊途同归。对不同的 iterator 类型做了重载。

`__find_if` 对 InputIterator 和 RandomAccessIterator 分别做了重载
{% highlight cpp %}
  template<typename _InputIterator, typename _Predicate>
    inline _InputIterator
    __find_if(_InputIterator __first, _InputIterator __last,
              _Predicate __pred, input_iterator_tag)
    {
      while (__first != __last && !__pred(__first))
        ++__first;
      return __first;
    }
{% endhighlight %}

而针对 RandomAccessIterator，`__find_if` 主动做了 [loop unroll](http://en.wikipedia.org/wiki/Loop_unwinding) 。

{% highlight cpp %}
  template<typename _RandomAccessIterator, typename _Predicate>
    _RandomAccessIterator
    __find_if(_RandomAccessIterator __first, _RandomAccessIterator __last,
              _Predicate __pred, random_access_iterator_tag)
    {
      typename iterator_traits<_RandomAccessIterator>::difference_type
        __trip_count = (__last - __first) >> 2;
      for (; __trip_count > 0; --__trip_count)
        {
          if (__pred(__first))
            return __first;
          ++__first;
          if (__pred(__first))
            return __first;
          ++__first;
          if (__pred(__first))
            return __first;
          ++__first;
          if (__pred(__first))
            return __first;
          ++__first;
        }

      switch (__last - __first)
        {
        case 3:
          if (__pred(__first))
            return __first;
          ++__first;
        case 2:
          if (__pred(__first))
            return __first;
          ++__first;
        case 1:
          if (__pred(__first))
            return __first;
          ++__first;
        case 0:
        default:
          return __last;
        }
    }
{% endhighlight %}

`for_each` 就没什么好说的了。`for_each` 最后悔把传进来的 Function 再返回回去。

{% highlight cpp %}
  template<typename _InputIterator, typename _Function>
    _Function
    for_each(_InputIterator __first, _InputIterator __last, _Function __f)
    {
      // concept requirements
      __glibcxx_function_requires(_InputIteratorConcept<_InputIterator>)
      __glibcxx_requires_valid_range(__first, __last);
      for (; __first != __last; ++__first)
        __f(*__first);
      return _GLIBCXX_MOVE(__f);
    }
{% endhighlight %}

`count` 和 `count_if` 跟之前的 `find` 的道理差不多，两个都可以统一到一个过程中。

{% highlight cpp %}
  template<typename _InputIterator, typename _Tp>
    inline typename iterator_traits<_InputIterator>::difference_type
    count(_InputIterator __first, _InputIterator __last, const _Tp& __value)
    {
      // concept requirements
      __glibcxx_function_requires(_InputIteratorConcept<_InputIterator>)
      __glibcxx_function_requires(_EqualOpConcept<
            typename iterator_traits<_InputIterator>::value_type, _Tp>)
      __glibcxx_requires_valid_range(__first, __last);
      return std::__count_if(__first, __last,
                             __gnu_cxx::__ops::__iter_equals_val(__value));
    }

  template<typename _InputIterator, typename _Predicate>
    inline typename iterator_traits<_InputIterator>::difference_type
    count_if(_InputIterator __first, _InputIterator __last, _Predicate __pred)
    {
      // concept requirements
      __glibcxx_function_requires(_InputIteratorConcept<_InputIterator>)
      __glibcxx_function_requires(_UnaryPredicateConcept<_Predicate,
            typename iterator_traits<_InputIterator>::value_type>)
      __glibcxx_requires_valid_range(__first, __last);
      return std::__count_if(__first, __last,
                             __gnu_cxx::__ops::__pred_iter(__pred));
    }

  template<typename _InputIterator, typename _Predicate>
    typename iterator_traits<_InputIterator>::difference_type
    __count_if(_InputIterator __first, _InputIterator __last, _Predicate __pred)
    {
      typename iterator_traits<_InputIterator>::difference_type __n = 0;
      for (; __first != __last; ++__first)
        if (__pred(__first))
          ++__n;
      return __n;
    }
{% endhighlight %}

不过在这里没有做 loop unroll。其实刚才也有一些怀疑，loop unroll 究竟能起到什么作用呢？以 4 为 factor unroll 又是为什么呢？这个疑问先留下，继续往下看。

`mismatch`  就是从两个 iterator 开始逐个比较，return 第一个 mismatch 的 pair 的 iterator。mismatch 分别有带 Predicate 的版本x2，带 iterator last2 的版本x2 一共四个重载版本。相似的情况可以化归。

先是不带 iterator last2 的（通过就是 first1 - last1，first2 指定两个范围）
{% highlight cpp %}
  template<typename _InputIterator1, typename _InputIterator2,
           typename _BinaryPredicate>
    inline pair<_InputIterator1, _InputIterator2>
    mismatch(_InputIterator1 __first1, _InputIterator1 __last1,
             _InputIterator2 __first2, _InputIterator2 __last2,
             _BinaryPredicate __binary_pred)
    {
      // concept requirements
      __glibcxx_function_requires(_InputIteratorConcept<_InputIterator1>)
      __glibcxx_function_requires(_InputIteratorConcept<_InputIterator2>)
      __glibcxx_requires_valid_range(__first1, __last1);
      __glibcxx_requires_valid_range(__first2, __last2);
      return _GLIBCXX_STD_A::__mismatch(__first1, __last1, __first2, __last2,
                             __gnu_cxx::__ops::__iter_comp_iter(__binary_pred));
    }

  template<typename _InputIterator1, typename _InputIterator2,
           typename _BinaryPredicate>
    pair<_InputIterator1, _InputIterator2>
    __mismatch(_InputIterator1 __first1, _InputIterator1 __last1,
               _InputIterator2 __first2, _BinaryPredicate __binary_pred)
    {
      while (__first1 != __last1 && __binary_pred(__first1, __first2))
        {
          ++__first1;
          ++__first2;
        }
      return pair<_InputIterator1, _InputIterator2>(__first1, __first2);
    }
{% endhighlight %}
然后是带 iterator last2 的（通过就是 first1 - last1，first2-last2 指定两个范围）

{% highlight cpp %}
  template<typename _InputIterator1, typename _InputIterator2,
           typename _BinaryPredicate>
    inline pair<_InputIterator1, _InputIterator2>
    mismatch(_InputIterator1 __first1, _InputIterator1 __last1,
             _InputIterator2 __first2, _InputIterator2 __last2,
             _BinaryPredicate __binary_pred)
    {
      // concept requirements
      __glibcxx_function_requires(_InputIteratorConcept<_InputIterator1>)
      __glibcxx_function_requires(_InputIteratorConcept<_InputIterator2>)
      __glibcxx_requires_valid_range(__first1, __last1);
      __glibcxx_requires_valid_range(__first2, __last2);
      return _GLIBCXX_STD_A::__mismatch(__first1, __last1, __first2, __last2,
                             __gnu_cxx::__ops::__iter_comp_iter(__binary_pred));
    }

  template<typename _InputIterator1, typename _InputIterator2,
           typename _BinaryPredicate>
    pair<_InputIterator1, _InputIterator2>
    __mismatch(_InputIterator1 __first1, _InputIterator1 __last1,
               _InputIterator2 __first2, _InputIterator2 __last2,
               _BinaryPredicate __binary_pred)
    {
      while (__first1 != __last1 && __first2 != __last2
             && __binary_pred(__first1, __first2))
        {
          ++__first1;
          ++__first2;
        }
      return pair<_InputIterator1, _InputIterator2>(__first1, __first2);
    }
{% endhighlight %}

似乎 concept check 占了绝大篇幅。。。`mismatch` 搞定，接下来是 `equal`。equal 是比较两段 iterator range 上是不是全部 equal。

对于 RAI，equal 也做了特殊处理，直接检查是不是 range 长度相同，然后再进入 equal(first1, last1, first2) 做比较。而对于不是 RAI 的 iterator 则直接逐个比较。

{% highlight cpp %}
  template<typename _II1, typename _II2>
    inline bool
    equal(_II1 __first1, _II1 __last1, _II2 __first2, _II2 __last2)
    {
      // concept requirements
      __glibcxx_function_requires(_InputIteratorConcept<_II1>)
      __glibcxx_function_requires(_InputIteratorConcept<_II2>)
      __glibcxx_function_requires(_EqualOpConcept<
            typename iterator_traits<_II1>::value_type,
            typename iterator_traits<_II2>::value_type>)
      __glibcxx_requires_valid_range(__first1, __last1);
      __glibcxx_requires_valid_range(__first2, __last2);
      using _RATag = random_access_iterator_tag;
      using _Cat1 = typename iterator_traits<_II1>::iterator_category;
      using _Cat2 = typename iterator_traits<_II2>::iterator_category;
      using _RAIters = __and_<is_same<_Cat1, _RATag>, is_same<_Cat2, _RATag>>;
      if (_RAIters())
        {
          auto __d1 = std::distance(__first1, __last1);
          auto __d2 = std::distance(__first2, __last2);
          if (__d1 != __d2)
            return false;
          return _GLIBCXX_STD_A::equal(__first1, __last1, __first2);
        }
      for (; __first1 != __last1 && __first2 != __last2; ++__first1, ++__first2)
        if (!(*__first1 == *__first2))
          return false;
      return __first1 == __last1 && __first2 == __last2;
    }
{% endhighlight %}

equal(first1, last1, first2, last2) 和 equal(first1, last1, first2, last2, predicate) 之间代码几乎一模一样，唯一不同就是调用了 equal(first1, last1, first2)，equal(first1, last1, first2, predicate)。为什么这么做呢？

{% highlight cpp %}
  template<typename _II1, typename _II2>
    inline bool
    equal(_II1 __first1, _II1 __last1, _II2 __first2)
    {
      // concept requirements
      __glibcxx_function_requires(_InputIteratorConcept<_II1>)
      __glibcxx_function_requires(_InputIteratorConcept<_II2>)
      __glibcxx_function_requires(_EqualOpConcept<
            typename iterator_traits<_II1>::value_type,
            typename iterator_traits<_II2>::value_type>)
      __glibcxx_requires_valid_range(__first1, __last1);
      return std::__equal_aux(std::__niter_base(__first1),
                              std::__niter_base(__last1),
                              std::__niter_base(__first2));
    }
  template<typename _IIter1, typename _IIter2, typename _BinaryPredicate>
    inline bool
    equal(_IIter1 __first1, _IIter1 __last1,
          _IIter2 __first2, _BinaryPredicate __binary_pred)
    {
      // concept requirements
      __glibcxx_function_requires(_InputIteratorConcept<_IIter1>)
      __glibcxx_function_requires(_InputIteratorConcept<_IIter2>)
      __glibcxx_requires_valid_range(__first1, __last1);
      for (; __first1 != __last1; ++__first1, ++__first2)
        if (!bool(__binary_pred(*__first1, *__first2)))
          return false;
      return true;
    }
{% endhighlight %}

带 predicate 的 equal 仍然走的是老路线，逐个 check，如果不带 predicate 呢？跑到 `__equal_aux` 里面。

{% highlight cpp %}
  // If _Iterator is a __normal_iterator return its base (a plain pointer,
  // normally) otherwise return it untouched. See copy, fill, ...
  template<typename _Iterator>
    struct _Niter_base
    : _Iter_base<_Iterator, __is_normal_iterator<_Iterator>::__value>
    { };
  template<typename _Iterator>
    inline typename _Niter_base<_Iterator>::iterator_type
    __niter_base(_Iterator __it)
    { return std::_Niter_base<_Iterator>::_S_base(__it); }
{% endhighlight %}

如果 iterator 有 base type 的话，就把 base 拿出来。对于日常的 iterator，在这里我们得到了指针。

{% highlight cpp %}
  template<bool _BoolType>
    struct __equal
    {
      template<typename _II1, typename _II2>
        static bool
        equal(_II1 __first1, _II1 __last1, _II2 __first2)
        {
          for (; __first1 != __last1; ++__first1, ++__first2)
            if (!(*__first1 == *__first2))
              return false;
          return true;
        }
    };
  template<>
    struct __equal<true>
    {
      template<typename _Tp>
        static bool
        equal(const _Tp* __first1, const _Tp* __last1, const _Tp* __first2)
        {
          return !__builtin_memcmp(__first1, __first2, sizeof(_Tp)
                                   * (__last1 - __first1));
        }
    };

  template<typename _II1, typename _II2>
    inline bool
    __equal_aux(_II1 __first1, _II1 __last1, _II2 __first2)
    {
      typedef typename iterator_traits<_II1>::value_type _ValueType1;
      typedef typename iterator_traits<_II2>::value_type _ValueType2;
      const bool __simple = ((__is_integer<_ValueType1>::__value
                              || __is_pointer<_ValueType1>::__value)
                             && __is_pointer<_II1>::__value
                             && __is_pointer<_II2>::__value
                             && __are_same<_ValueType1, _ValueType2>::__value);
      return std::__equal<__simple>::equal(__first1, __last1, __first2);
    }
{% endhighlight %}

原来是在做这种变态的事情，如果两个是同类型的指针的话而且指向整数类型，就直接上 memcmp 。还是通过模板做静态的选择。

接下来是 range 的查找。`find_end` 是 finds the last sequence of elements in a certain range，翻译起来感觉怪怪的。。。为了节省篇幅，就把 concept check 去掉了。。

{% highlight cpp %}
  template<typename _ForwardIterator1, typename _ForwardIterator2>
    inline _ForwardIterator1
    find_end(_ForwardIterator1 __first1, _ForwardIterator1 __last1,
             _ForwardIterator2 __first2, _ForwardIterator2 __last2)
    {
      return std::__find_end(__first1, __last1, __first2, __last2,
                             std::__iterator_category(__first1),
                             std::__iterator_category(__first2),
                             __gnu_cxx::__ops::__iter_equal_to_iter());
    }

  template<typename _ForwardIterator1, typename _ForwardIterator2,
           typename _BinaryPredicate>
    inline _ForwardIterator1
    find_end(_ForwardIterator1 __first1, _ForwardIterator1 __last1,
             _ForwardIterator2 __first2, _ForwardIterator2 __last2,
             _BinaryPredicate __comp)
    {
      return std::__find_end(__first1, __last1, __first2, __last2,
                             std::__iterator_category(__first1),
                             std::__iterator_category(__first2),
                             __gnu_cxx::__ops::__iter_comp_iter(__comp));
    }
{% endhighlight %}

再到 `__find_end`。想一想这里可以做什么优化呢？注意到这里把 iterator_category 传了进去。`find_end` 当然是从后往前找，不过这里拿的是 iterator，并不是一定可以从后往前。单纯 FowardIterator 做不到这一点，不过 BidirectionalIterator 做的到。

{% highlight cpp %}
  template<typename _ForwardIterator1, typename _ForwardIterator2,
           typename _BinaryPredicate>
    _ForwardIterator1
    __find_end(_ForwardIterator1 __first1, _ForwardIterator1 __last1,
               _ForwardIterator2 __first2, _ForwardIterator2 __last2,
               forward_iterator_tag, forward_iterator_tag,
               _BinaryPredicate __comp)
    {
      if (__first2 == __last2)
        return __last1;

      _ForwardIterator1 __result = __last1;
      while (1)
        {
          _ForwardIterator1 __new_result
            = std::__search(__first1, __last1, __first2, __last2, __comp);
          if (__new_result == __last1)
            return __result;
          else
            {
              __result = __new_result;
              __first1 = __new_result;
              ++__first1;
            }
        }
    }

  template<typename _BidirectionalIterator1, typename _BidirectionalIterator2,
           typename _BinaryPredicate>
    _BidirectionalIterator1
    __find_end(_BidirectionalIterator1 __first1,
               _BidirectionalIterator1 __last1,
               _BidirectionalIterator2 __first2,
               _BidirectionalIterator2 __last2,
               bidirectional_iterator_tag, bidirectional_iterator_tag,
               _BinaryPredicate __comp)
    {
      typedef reverse_iterator<_BidirectionalIterator1> _RevIterator1;
      typedef reverse_iterator<_BidirectionalIterator2> _RevIterator2;

      _RevIterator1 __rlast1(__first1);
      _RevIterator2 __rlast2(__first2);
      _RevIterator1 __rresult = std::__search(_RevIterator1(__last1), __rlast1,
                                              _RevIterator2(__last2), __rlast2,
                                              __comp);

      if (__rresult == __rlast1)
        return __last1;
      else
        {
          _BidirectionalIterator1 __result = __rresult.base();
          std::advance(__result, -std::distance(__first2, __last2));
          return __result;
        }
    }
{% endhighlight %}

如果只是 FowardIterator 的话，就只能从头开始找，然后慢慢 advance first。bidirectionalIterator 直接利用 ReverseIterator 做从后向前查找。。。 原来 ReverseIterator 是这么用的啊~~~

`find_first_of` 是找 range 里是否存在另外一个 range 里面任意一个元素。。。代码冗余了。。。其实根据之前的方法，可以统一到一起。另外一个槽点是名字让人很迷惑，`find_end` 跟 `find_first_of` 这些名字起得都特别模糊，不看解释基本猜不出意思。。

{% highlight cpp %}
  template<typename _InputIterator, typename _ForwardIterator>
    _InputIterator
    find_first_of(_InputIterator __first1, _InputIterator __last1,
                  _ForwardIterator __first2, _ForwardIterator __last2)
    {
      for (; __first1 != __last1; ++__first1)
        for (_ForwardIterator __iter = __first2; __iter != __last2; ++__iter)
          if (*__first1 == *__iter)
            return __first1;
      return __last1;
    }

  template<typename _InputIterator, typename _ForwardIterator,
           typename _BinaryPredicate>
    _InputIterator
    find_first_of(_InputIterator __first1, _InputIterator __last1,
                  _ForwardIterator __first2, _ForwardIterator __last2,
                  _BinaryPredicate __comp)
    {
      for (; __first1 != __last1; ++__first1)
        for (_ForwardIterator __iter = __first2; __iter != __last2; ++__iter)
          if (__comp(*__first1, *__iter))
            return __first1;
      return __last1;
    }
{% endhighlight %}

刚才看到里面调用了 `std::__search`，实际上就是 `std::search`。我觉得 `std::search` 可以起名叫 `std::find_first` 其实。。这里的名字起得真是乱。

{% highlight cpp %}
  template<typename _ForwardIterator1, typename _ForwardIterator2,
           typename _BinaryPredicate>
    inline _ForwardIterator1
    search(_ForwardIterator1 __first1, _ForwardIterator1 __last1,
           _ForwardIterator2 __first2, _ForwardIterator2 __last2,
           _BinaryPredicate __predicate)
    {
      return std::__search(__first1, __last1, __first2, __last2,
                           __gnu_cxx::__ops::__iter_comp_iter(__predicate));
    }
{% endhighlight %}

{% highlight cpp %}
  template<typename _ForwardIterator1, typename _ForwardIterator2,
           typename _BinaryPredicate>
    _ForwardIterator1
    __search(_ForwardIterator1 __first1, _ForwardIterator1 __last1,
             _ForwardIterator2 __first2, _ForwardIterator2 __last2,
             _BinaryPredicate __predicate)
    {
      // Test for empty ranges
      if (__first1 == __last1 || __first2 == __last2)
        return __first1;

      // Test for a pattern of length 1.
      _ForwardIterator2 __p1(__first2);
      if (++__p1 == __last2)
        return std::__find_if(__first1, __last1,
                __gnu_cxx::__ops::__iter_comp_iter(__predicate, __first2));

      // General case.
      _ForwardIterator2 __p;
      _ForwardIterator1 __current = __first1;

      for (;;)
        {
          __first1 =
            std::__find_if(__first1, __last1,
                __gnu_cxx::__ops::__iter_comp_iter(__predicate, __first2));

          if (__first1 == __last1)
            return __last1;

          __p = __p1;
          __current = __first1;
          if (++__current == __last1)
            return __last1;

          while (__predicate(__current, __p))
            {
              if (++__p == __last2)
                return __first1;
              if (++__current == __last1)
                return __last1;
            }
          ++__first1;
        }
      return __first1;
    }
{% endhighlight %}

`__search` 对长度为 1 的 pattern 有个小优化。剩下的就强上了，有木有种 strstr 的既视感，代码很清晰~不过优化还不到 kmp 那么变态，毕竟这里只是 ForwardIterator（有种弄个 RAI 的优化啊 lol 变态的 STL）。

`search_n` 是找到长度为 n 的相同元素的一个 sequance。

{% highlight cpp %}
  template<typename _ForwardIterator, typename _Integer, typename _Tp,
           typename _BinaryPredicate>
    inline _ForwardIterator
    search_n(_ForwardIterator __first, _ForwardIterator __last,
             _Integer __count, const _Tp& __val,
             _BinaryPredicate __binary_pred)
    {
      return std::__search_n(__first, __last, __count,
                __gnu_cxx::__ops::__iter_comp_val(__binary_pred, __val));
    }
{% endhighlight %}

{% highlight cpp %}
  template<typename _ForwardIterator, typename _Integer,
           typename _UnaryPredicate>
    _ForwardIterator
    __search_n(_ForwardIterator __first, _ForwardIterator __last,
               _Integer __count,
               _UnaryPredicate __unary_pred)
    {
      if (__count <= 0)
        return __first;

      if (__count == 1)
        return std::__find_if(__first, __last, __unary_pred);

      return std::__search_n_aux(__first, __last, __count, __unary_pred,
                                 std::__iterator_category(__first));
    }
{% endhighlight %}
对 count == 1 的情况直接去找 `__find_if` 。反正是返回第一个。这里又要托管给 aux 类似物，要对不同类 iterator 做处理，会有什么优化呢？ yy 一下就知道。

{% highlight cpp %}
  template<typename _ForwardIterator, typename _Integer,
           typename _UnaryPredicate>
    _ForwardIterator
    __search_n_aux(_ForwardIterator __first, _ForwardIterator __last,
                   _Integer __count, _UnaryPredicate __unary_pred,
                   std::forward_iterator_tag)
    {
      __first = std::__find_if(__first, __last, __unary_pred);
      while (__first != __last)
        {
          typename iterator_traits<_ForwardIterator>::difference_type
            __n = __count;
          _ForwardIterator __i = __first;
          ++__i;
          while (__i != __last && __n != 1 && __unary_pred(__i))
            {
              ++__i;
              --__n;
            }
          if (__n == 1)
            return __first;
          if (__i == __last)
            return __last;
          __first = std::__find_if(++__i, __last, __unary_pred);
        }
      return __last;
    }
{% endhighlight %}

如果是 RAI 的话，可以根据 distance 提前终止搜索，而且不用保存当前搜索的位置。这还是提前 advance count 个位置，然后从后向前查找是不是满足 count 个。

{% highlight cpp %}
  template<typename _RandomAccessIter, typename _Integer,
           typename _UnaryPredicate>
    _RandomAccessIter
    __search_n_aux(_RandomAccessIter __first, _RandomAccessIter __last,
                   _Integer __count, _UnaryPredicate __unary_pred,
                   std::random_access_iterator_tag)
    {
      typedef typename std::iterator_traits<_RandomAccessIter>::difference_type
        _DistanceType;

      _DistanceType __tailSize = __last - __first;
      _DistanceType __remainder = __count;

      while (__remainder <= __tailSize) // the main loop...
        {
          __first += __remainder;
          __tailSize -= __remainder;
          // __first here is always pointing to one past the last element of
          // next possible match.
          _RandomAccessIter __backTrack = __first;
          while (__unary_pred(--__backTrack))
            {
              if (--__remainder == 0)
                return (__first - __count); // Success
            }
          __remainder = __count + 1 - (__first - __backTrack);
        }
      return __last; // Failure
    }
{% endhighlight %}

最后还有一个 `adjancent_find`。

{% highlight cpp %}
  template<typename _ForwardIterator, typename _BinaryPredicate>
    _ForwardIterator
    __adjacent_find(_ForwardIterator __first, _ForwardIterator __last,
                    _BinaryPredicate __binary_pred)
    {
      if (__first == __last)
        return __last;
      _ForwardIterator __next = __first;
      while (++__next != __last)
        {
          if (__binary_pred(__first, __next))
            return __first;
          __first = __next;
        }
      return __last;
    }
{% endhighlight %}

对了，最后必须要提一下 `<algorithm>` 里面的注释，也和代码一样漂亮，而且非常完善。举个例子。
{% highlight cpp %}
  /**
   * @brief Remove elements from a sequence.
   * @ingroup mutating_algorithms
   * @param __first An input iterator.
   * @param __last An input iterator.
   * @param __value The value to be removed.
   * @return An iterator designating the end of the resulting sequence.
   *
   * All elements equal to @p __value are removed from the range
   * @p [__first,__last).
   *
   * remove() is stable, so the relative order of elements that are
   * not removed is unchanged.
   *
   * Elements between the end of the resulting sequence and @p __last
   * are still present, but their value is unspecified.
  */
{% endhighlight %}

### 总结一下
1. algorithm 针对 iterator category 做优化
2. `<algorithm>` 无论是代码还是注释都非常简洁明了，值得学习啊~ 而且实现也是非常好的练习。
3. 如何证明这里代码的正确性呢？也是非常好的练习。
