#lang pycket #:stdlib

(require racket/private/for)

(provide check my-len max-val)

(define my-len 100)
(define max-val 100)

(define check
  (lambda (v)
    (chaperone-vector v
      (lambda (vec i val)
        (unless (and (>= val 0) (<= val max-val))
          (error 'check-ref "Check is out of bounds in ref"))
        val)
      (lambda (vec i val)
        (unless (and (>= val 0) (<= val max-val))
          (error 'check-set "Check is out of bounds in set"))
        val))))

(define my-vec (make-vector my-len))
(define imp-vec (check (make-vector my-len)))
(define imp-imp-vec (check (check (make-vector my-len))))
(define imp-imp-imp-vec (check (check (check (make-vector my-len)))))

(define (repeat f n)
  (if (eqv? n 0)
    (void)
    (begin (f) (repeat f (sub1 n)))))

(define (iota n)
  (define (loop z)
    (if (eqv? n z) '() (cons z (loop (+ z 1)))))
  (loop 0))

(define inplace-map
  (lambda (vec)
    (for-each
      (lambda (n)
        (repeat
          (lambda () (vector-set! vec n (+ (vector-ref vec n) 1)))
          max-val))
      (iota my-len))))

(display "\nSlow ref/set benchmark\n")
; Timing for no chaperoning
(time (inplace-map my-vec))

;; Timing for single chaperoning
(time (inplace-map imp-vec))

;; Timing for double chaperoning
(time (inplace-map imp-imp-vec))

;; Timing for triple chaperones
(time (inplace-map imp-imp-imp-vec))

(display "\nSam's Fast ref/set benchmark\n")

(define my-vec2 (make-vector my-len))
(define imp-vec2 (check (make-vector my-len)))
(define imp-imp-vec2 (check (check (make-vector my-len))))
(define imp-imp-imp-vec2 (check (check (check (make-vector my-len)))))

(time
  (for ([n (in-range my-len)])
       (for ([_ (in-range max-val)])
            (vector-set! my-vec2 n (+ (vector-ref my-vec2 n) 1)))))

(time
  (for ([n (in-range my-len)])
       (for ([_ (in-range max-val)])
            (vector-set! imp-vec2 n (+ (vector-ref imp-vec2 n) 1)))))

(time
  (for ([n (in-range my-len)])
       (for ([_ (in-range max-val)])
            (vector-set! imp-imp-vec2 n (+ (vector-ref imp-imp-vec2 n) 1)))))

(time
  (for ([n (in-range my-len)])
       (for ([_ (in-range max-val)])
            (vector-set! imp-imp-imp-vec2 n (+ (vector-ref imp-imp-imp-vec2 n) 1)))))

(define summation1
  (lambda (vec)
    (let ([acc 0])
      (for-each
        (lambda (i)
          (set! acc (+ acc (vector-ref vec i))))
        (iota (vector-length vec)))
      acc)))

(define summation2
  (lambda (vec)
    (let ([acc 0])
      (for ([n (in-range (vector-length vec))])
        (set! acc (+ acc (vector-ref vec n))))
      acc)))

(display "\nSummation of vectors\n")
(time (summation1 my-vec))
(time (summation1 imp-vec))
(time (summation1 imp-imp-vec))
(time (summation1 imp-imp-imp-vec))

(display "\nSummation of vectors 2\n")
(time (summation2 my-vec))
(time (summation2 imp-vec))
(time (summation2 imp-imp-vec))
(time (summation2 imp-imp-imp-vec))

