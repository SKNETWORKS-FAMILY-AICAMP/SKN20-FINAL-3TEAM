package com.example.skn20.service;

import com.example.skn20.classes.UD;
import com.example.skn20.entity.User;
import com.example.skn20.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;

@Service
@RequiredArgsConstructor
public class UserService implements UserDetailsService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    @Override
    public UserDetails loadUserByUsername(String email) throws UsernameNotFoundException {
        User user = userRepository.findByEmail(email);
        if (user == null) {
            throw new UsernameNotFoundException("User not found: " + email);
        }
        return new UD(user);
    }

    @Transactional
    public User registerUser(String email, String password, String name, String phonenumber) {
        if (userRepository.existsByEmail(email)) {
            throw new RuntimeException("이미 존재하는 이메일입니다.");
        }

        User user = User.builder()
                .email(email)
                .pw(passwordEncoder.encode(password))
                .name(name)
                .phonenumber(phonenumber)
                .create_at(LocalDate.now())
                .role("USER")
                .build();

        return userRepository.save(user);
    }

    @Transactional
    public User updateProfile(String email, String name, String phonenumber) {
        User user = userRepository.findByEmail(email);
        if (user == null) {
            throw new UsernameNotFoundException("User not found: " + email);
        }

        user.setName(name);
        user.setPhonenumber(phonenumber);
        user.setUpdate_at(LocalDate.now());

        return userRepository.save(user);
    }

    public User findByEmail(String email) {
        return userRepository.findByEmail(email);
    }

    @Transactional
    public void changePassword(String email, String newPassword) {
        User user = userRepository.findByEmail(email);
        if (user == null) {
            throw new UsernameNotFoundException("User not found: " + email);
        }
        user.setPw(passwordEncoder.encode(newPassword));
        user.setUpdate_at(LocalDate.now());
        userRepository.save(user);
    }
}

