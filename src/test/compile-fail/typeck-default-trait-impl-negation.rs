// Copyright 2015 The Rust Project Developers. See the COPYRIGHT
// file at the top-level directory of this distribution and at
// http://rust-lang.org/COPYRIGHT.
//
// Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
// http://www.apache.org/licenses/LICENSE-2.0> or the MIT license
// <LICENSE-MIT or http://opensource.org/licenses/MIT>, at your
// option. This file may not be copied, modified, or distributed
// except according to those terms.

#![feature(optin_builtin_traits)]

trait MyTrait {}

impl MyTrait for .. {}

unsafe trait MyUnsafeTrait {}

unsafe impl MyUnsafeTrait for .. {}

struct ThisImplsTrait;

impl !MyUnsafeTrait for ThisImplsTrait {}


struct ThisImplsUnsafeTrait;

impl !MyTrait for ThisImplsUnsafeTrait {}

fn is_my_trait<T: MyTrait>() {}
fn is_my_unsafe_trait<T: MyUnsafeTrait>() {}

fn main() {
    is_my_trait::<ThisImplsTrait>();
    is_my_trait::<ThisImplsUnsafeTrait>();
    //~^ ERROR the trait `MyTrait` is not implemented for the type `ThisImplsUnsafeTrait`

    is_my_unsafe_trait::<ThisImplsTrait>();
    //~^ ERROR the trait `MyUnsafeTrait` is not implemented for the type `ThisImplsTrait`

    is_my_unsafe_trait::<ThisImplsUnsafeTrait>();
}
